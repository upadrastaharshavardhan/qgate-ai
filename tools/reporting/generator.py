"""Generate JSON, Markdown, and HTML reports."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.models.decision import GateDecision
from core.models.report import QualityGateReport
from core.models.repository import RepositoryProfile
from core.models.change import ChangeSummary
from core.state.quality_gate_state import QualityGateState

logger = logging.getLogger(__name__)


class ReportGenerator:
    def __init__(self, output_dir: str | Path = ".qgate/reports") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def from_state(self, state: QualityGateState) -> QualityGateReport:
        decision_data = state.get("gate_decision") or {}
        decision = GateDecision.model_validate(decision_data) if decision_data else GateDecision(
            decision="PASS",  # type: ignore
            final_reason="No decision",
        )
        profile = None
        if state.get("repository_profile"):
            profile = RepositoryProfile.model_validate(state["repository_profile"])
        change = None
        if state.get("change_summary"):
            change = ChangeSummary.model_validate(state["change_summary"])

        all_findings = []
        for key in (
            "quality_findings",
            "security_findings",
            "architecture_findings",
            "dependency_findings",
            "regression_findings",
            "ai_review_findings",
            "historical_findings",
            "blocking_findings",
            "warnings",
        ):
            all_findings.extend(state.get(key) or [])

        return QualityGateReport(
            report_id=str(uuid4()),
            repository_path=state.get("repository_path", ""),
            decision=decision,
            repository_profile=profile,
            change_summary=change,
            all_findings=all_findings,  # type: ignore
            audit_events=state.get("audit_events") or [],
            execution_timeline=state.get("execution_timeline") or {},
        )

    def write_json(self, report: QualityGateReport, name: str = "qgate-report.json") -> Path:
        path = self.output_dir / name
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return path

    def write_markdown(self, report: QualityGateReport, name: str = "qgate-report.md") -> Path:
        path = self.output_dir / name
        d = report.decision
        lines = [
            "# Q-GATE AI Report",
            "",
            f"**Generated:** {report.generated_at.isoformat()}",
            f"**Repository:** `{report.repository_path}`",
            "",
            "## Decision",
            "",
            f"**{d.decision.value}**",
            "",
            f"- Quality Score: **{d.quality_score:.1f}/100**",
            f"- Risk Score: **{d.risk_score:.1f}/100**",
            f"- Confidence: **{d.confidence:.0%}**",
            f"- Reason: {d.final_reason}",
            "",
            "## Change Summary",
            "",
        ]
        if report.change_summary:
            cs = report.change_summary
            lines.extend(
                [
                    f"- Base: `{cs.base_commit[:8]}`",
                    f"- Head: `{cs.head_commit[:8]}`",
                    f"- Files changed: {len(cs.changed_files)}",
                    f"- +{cs.total_additions} / -{cs.total_deletions}",
                    f"- Message: {cs.commit_message[:200]}",
                    "",
                ]
            )

        if d.blocking_findings:
            lines.append("## Blocking Findings")
            lines.append("")
            for f in d.blocking_findings:
                lines.append(f"- **[{f.severity.value.upper()}]** {f.title}")
                lines.append(f"  - {f.description}")
                if f.recommendation:
                    lines.append(f"  - Recommendation: {f.recommendation}")
            lines.append("")

        if d.warnings:
            lines.append("## Warnings")
            lines.append("")
            for f in d.warnings:
                lines.append(f"- **[{f.severity.value.upper()}]** {f.title}")
            lines.append("")

        if d.recommendations:
            lines.append("## Recommendations")
            lines.append("")
            for r in d.recommendations:
                lines.append(f"- {r}")
            lines.append("")

        if report.execution_timeline:
            lines.append("## Execution Timeline")
            lines.append("")
            for k, v in report.execution_timeline.items():
                lines.append(f"- {k}: {v}s")
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def write_html(self, report: QualityGateReport, name: str = "qgate-report.html") -> Path:
        path = self.output_dir / name
        d = report.decision
        color = {
            "PASS": "#22c55e",
            "PASS_WITH_WARNINGS": "#eab308",
            "BLOCK": "#ef4444",
        }.get(d.decision.value, "#6b7280")

        blocking_html = ""
        for f in d.blocking_findings:
            blocking_html += f"<li><strong>[{f.severity.value}]</strong> {f.title}<br/><small>{f.description}</small></li>"

        warnings_html = ""
        for f in d.warnings:
            warnings_html += f"<li><strong>[{f.severity.value}]</strong> {f.title}</li>"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Q-GATE AI Report</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; background: #0f172a; color: #e2e8f0; }}
    h1 {{ color: #38bdf8; }}
    .badge {{ display: inline-block; padding: 0.5rem 1.5rem; border-radius: 0.5rem; font-weight: 700; font-size: 1.25rem; background: {color}; color: #0f172a; }}
    .score {{ display: inline-block; margin-right: 1.5rem; }}
    .score span {{ font-size: 1.5rem; font-weight: 700; }}
    section {{ margin: 1.5rem 0; padding: 1rem; background: #1e293b; border-radius: 0.5rem; }}
    ul {{ padding-left: 1.25rem; }}
    code {{ background: #334155; padding: 0.1rem 0.4rem; border-radius: 0.25rem; }}
  </style>
</head>
<body>
  <h1>Q-GATE AI</h1>
  <p>Generated {report.generated_at.strftime("%Y-%m-%d %H:%M:%S")} UTC</p>
  <p>Repository: <code>{report.repository_path}</code></p>

  <section>
    <h2>Decision</h2>
    <div class="badge">{d.decision.value}</div>
    <p style="margin-top:1rem">{d.final_reason}</p>
    <div style="margin-top:1rem">
      <div class="score">Quality <span>{d.quality_score:.0f}</span>/100</div>
      <div class="score">Risk <span>{d.risk_score:.0f}</span>/100</div>
      <div class="score">Confidence <span>{d.confidence:.0%}</span></div>
    </div>
  </section>

  <section>
    <h2>Blocking Findings ({len(d.blocking_findings)})</h2>
    <ul>{blocking_html or "<li>None</li>"}</ul>
  </section>

  <section>
    <h2>Warnings ({len(d.warnings)})</h2>
    <ul>{warnings_html or "<li>None</li>"}</ul>
  </section>

  <section>
    <h2>Recommendations</h2>
    <ul>{"".join(f"<li>{r}</li>" for r in d.recommendations) or "<li>None</li>"}</ul>
  </section>
</body>
</html>"""
        path.write_text(html, encoding="utf-8")
        return path

    def generate_all(self, state: QualityGateState) -> dict[str, Path]:
        report = self.from_state(state)
        return {
            "json": self.write_json(report),
            "markdown": self.write_markdown(report),
            "html": self.write_html(report),
        }
