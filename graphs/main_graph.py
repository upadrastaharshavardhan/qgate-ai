"""Main Q-GATE LangGraph workflow (Phase 1–4)."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Literal

from langgraph.graph import END, START, StateGraph

from agents.architecture.agent import semantic_impact_node
from agents.code_review.agent import ai_code_review_node
from agents.dependency.agent import dependency_analysis_node
from agents.failure_investigator.agent import failure_investigator_node
from agents.git.agent import git_change_analysis_node
from agents.historical.agent import historical_intelligence_node, memory_persist_node
from agents.quality_gate.agent import quality_policy_node, risk_and_quality_scoring_node
from agents.regression.agent import regression_risk_node
from agents.repository.agent import repository_discovery_node
from agents.security.agent import security_analysis_node
from agents.test_impact.agent import test_impact_analysis_node
from agents.validation.agent import test_execution_node, validation_planner_node
from core.policies.config import load_config
from core.state.quality_gate_state import QualityGateState, create_initial_state
from tools.reporting.generator import ReportGenerator

logger = logging.getLogger(__name__)


def initialize_context_node(state: QualityGateState) -> dict[str, Any]:
    if not state.get("config"):
        cfg = load_config()
        return {"config": cfg.model_dump(), "phase": "init"}
    # Ensure memory block is present for get_memory_store
    cfg = state.get("config") or {}
    if "memory" not in cfg:
        raw = cfg.get("raw") or {}
        if "memory" in raw:
            cfg = {**cfg, "memory": raw["memory"]}
            return {"config": cfg, "phase": "init"}
    return {"phase": "init"}


def report_generator_node(state: QualityGateState) -> dict[str, Any]:
    config = state.get("config") or {}
    out_dir = config.get("output_dir") or ".qgate/reports"
    gen = ReportGenerator(out_dir)
    paths = gen.generate_all(state)
    audit = list(state.get("audit_events") or [])
    audit.append({"event": "report_generated", "paths": {k: str(v) for k, v in paths.items()}})
    return {"audit_events": audit, "phase": "report"}


def _merge_agent_updates(base: QualityGateState, updates: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    audit = list(base.get("audit_events") or [])
    timeline = dict(base.get("execution_timeline") or {})
    errors = list(base.get("errors") or [])

    for upd in updates:
        for key, value in upd.items():
            if key == "audit_events":
                for ev in value or []:
                    if ev not in audit:
                        audit.append(ev)
            elif key == "execution_timeline":
                timeline.update(value or {})
            elif key == "errors":
                errors.extend(value or [])
            elif key == "quality_findings":
                existing = list(merged.get("quality_findings") or base.get("quality_findings") or [])
                existing.extend(value or [])
                merged["quality_findings"] = existing
            else:
                merged[key] = value

    merged["audit_events"] = audit
    merged["execution_timeline"] = timeline
    if errors:
        merged["errors"] = errors
    return merged


def parallel_intelligence_node(state: QualityGateState) -> dict[str, Any]:
    start = time.perf_counter()
    agents: list[tuple[str, Callable[[QualityGateState], dict[str, Any]]]] = [
        ("security", security_analysis_node),
        ("dependency", dependency_analysis_node),
        ("code_review", ai_code_review_node),
        ("test_impact", test_impact_analysis_node),
        ("regression", regression_risk_node),
        ("historical", historical_intelligence_node),
    ]

    updates: list[dict[str, Any]] = []
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=min(6, len(agents))) as pool:
        futures = {pool.submit(fn, state): name for name, fn in agents}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                updates.append(fut.result())
            except Exception as e:
                logger.exception("Intelligence agent %s failed", name)
                errors.append(f"{name}: {e}")

    merged = _merge_agent_updates(state, updates)
    if errors:
        merged["errors"] = list(merged.get("errors") or []) + errors

    timeline = dict(merged.get("execution_timeline") or {})
    timeline["parallel_intelligence"] = round(time.perf_counter() - start, 3)
    merged["execution_timeline"] = timeline
    merged["phase"] = "parallel_intelligence"
    return merged


def route_after_tests(state: QualityGateState) -> Literal["failure_investigator", "scoring"]:
    results = state.get("test_results") or {}
    failed = int(results.get("failed") or 0) + int(results.get("errors") or 0)
    if failed > 0:
        return "failure_investigator"
    return "scoring"


def route_after_planner(state: QualityGateState) -> Literal["test_execution", "scoring"]:
    plan = state.get("validation_plan") or {}
    tests = state.get("tests_to_execute") or plan.get("unit_tests") or []
    if plan.get("skip_tests") or not tests:
        return "scoring"
    return "test_execution"


def build_main_graph() -> StateGraph:
    """Phase 4 graph: intelligence + validation + quality memory."""
    graph = StateGraph(QualityGateState)

    graph.add_node("initialize_context", initialize_context_node)
    graph.add_node("repository_discovery", repository_discovery_node)
    graph.add_node("git_change_analysis", git_change_analysis_node)
    graph.add_node("semantic_impact", semantic_impact_node)
    graph.add_node("parallel_intelligence", parallel_intelligence_node)
    graph.add_node("validation_planner", validation_planner_node)
    graph.add_node("test_execution", test_execution_node)
    graph.add_node("failure_investigator", failure_investigator_node)
    graph.add_node("scoring", risk_and_quality_scoring_node)
    graph.add_node("quality_policy", quality_policy_node)
    graph.add_node("memory_persist", memory_persist_node)
    graph.add_node("report_generator", report_generator_node)

    graph.add_edge(START, "initialize_context")
    graph.add_edge("initialize_context", "repository_discovery")
    graph.add_edge("repository_discovery", "git_change_analysis")
    graph.add_edge("git_change_analysis", "semantic_impact")
    graph.add_edge("semantic_impact", "parallel_intelligence")
    graph.add_edge("parallel_intelligence", "validation_planner")

    graph.add_conditional_edges(
        "validation_planner",
        route_after_planner,
        {"test_execution": "test_execution", "scoring": "scoring"},
    )
    graph.add_conditional_edges(
        "test_execution",
        route_after_tests,
        {"failure_investigator": "failure_investigator", "scoring": "scoring"},
    )
    graph.add_edge("failure_investigator", "scoring")
    graph.add_edge("scoring", "quality_policy")
    graph.add_edge("quality_policy", "memory_persist")
    graph.add_edge("memory_persist", "report_generator")
    graph.add_edge("report_generator", END)

    return graph


def run_quality_gate(
    repository_path: str,
    base: str = "main",
    head: str = "HEAD",
    source_branch: str | None = None,
    target_branch: str | None = None,
    config_path: str | None = None,
) -> QualityGateState:
    """Run the quality gate (Phase 1–4) and return final state."""
    config = load_config(config_path)
    cfg = config.model_dump()
    # Attach memory config from raw yaml
    if config.raw.get("memory"):
        cfg["memory"] = config.raw["memory"]
    initial = create_initial_state(
        repository_path=repository_path,
        base_commit=base,
        head_commit=head,
        source_branch=source_branch,
        target_branch=target_branch,
        config=cfg,
    )

    graph = build_main_graph()
    app = graph.compile()
    final: QualityGateState = app.invoke(initial)
    return final
