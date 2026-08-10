"""Q-GATE AI command-line interface."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

app = typer.Typer(
    name="qgate",
    help="Q-GATE AI — Intelligent Pre-Commit & CI Quality Gate",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


def _print_banner() -> None:
    console.print(
        Panel.fit(
            "[bold cyan]Q-GATE AI[/bold cyan]\n[dim]Intelligent Quality Gate[/dim]",
            border_style="cyan",
        )
    )


def _print_result(state: dict) -> int:
    """Pretty-print final result and return process exit code."""
    decision = state.get("final_decision") or "UNKNOWN"
    quality = float(state.get("quality_score") or 0)
    risk = float(state.get("risk_score") or 0)
    confidence = float(state.get("confidence_score") or 0)
    reason = state.get("final_reason") or ""
    changed = state.get("changed_files") or []
    blocking = state.get("blocking_findings") or []
    warnings = state.get("warnings") or []
    recommendations = state.get("recommendations") or []
    timeline = state.get("execution_timeline") or {}
    profile = state.get("repository_profile") or {}
    lang = (profile.get("language") or {}).get("primary", "unknown")

    color = {"PASS": "green", "PASS_WITH_WARNINGS": "yellow", "BLOCK": "red"}.get(decision, "white")

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("Repository", str(state.get("repository_path", "")))
    table.add_row("Language", lang)
    table.add_row("Base → Head", f"{str(state.get('base_commit', ''))[:8]} → {str(state.get('head_commit', ''))[:8]}")
    sec = state.get("security_findings") or []
    tests_exec = state.get("tests_to_execute") or []
    symbols = state.get("changed_symbols") or []
    table.add_row("Files Changed", str(len(changed)))
    table.add_row("Symbols Changed", str(len(symbols)))
    table.add_row("Security Findings", str(len(sec)))
    table.add_row("Tests Selected", str(len(tests_exec)))
    table.add_row("Quality Score", f"[bold]{quality:.0f}/100[/bold]")
    table.add_row("Risk Score", f"[bold]{risk:.0f}/100[/bold]")
    table.add_row("Confidence", f"{confidence:.0%}")
    hist = state.get("historical_context") or {}
    if hist.get("enabled"):
        table.add_row("Memory analyses", str(hist.get("analysis_count", 0)))
        if hist.get("hotspots"):
            table.add_row("Hotspots hit", str(len(hist.get("hotspots") or [])))
    console.print(table)
    console.print()

    decision_text = Text(f"  {decision}  ", style=f"bold white on {color}")
    console.print(decision_text)
    console.print(f"[dim]{reason}[/dim]")
    console.print()

    if blocking:
        console.print("[bold red]Blocking findings:[/bold red]")
        for f in blocking:
            console.print(f"  • [{f.get('severity', '?').upper()}] {f.get('title', '')}")
        console.print()

    if warnings:
        console.print("[bold yellow]Warnings:[/bold yellow]")
        for f in warnings[:10]:
            console.print(f"  • [{f.get('severity', '?').upper()}] {f.get('title', '')}")
        console.print()

    tr = state.get("test_results") or {}
    if tr.get("executed") or tr.get("failed"):
        console.print(
            f"[bold]Tests:[/bold] "
            f"✓ {tr.get('passed', 0)} passed  "
            f"✗ {tr.get('failed', 0)} failed  "
            f"executed={tr.get('executed', 0)}"
        )
        for ft in (tr.get("failed_tests") or [])[:5]:
            console.print(f"  ✗ {ft.get('nodeid', '?')}: {ft.get('message', '')[:80]}")
        console.print()

    inv = (state.get("historical_context") or {}).get("failure_investigations") or []
    if inv:
        console.print("[bold]Failure investigation:[/bold]")
        for i in inv[:5]:
            console.print(
                f"  • {i.get('classification')}: {i.get('test_nodeid')} "
                f"(confidence {float(i.get('confidence', 0)):.0%})"
            )
            if i.get("rationale"):
                console.print(f"    {i.get('rationale')[:120]}")
        console.print()

    if recommendations:
        console.print("[bold]Recommendations:[/bold]")
        for r in recommendations[:5]:
            console.print(f"  → {r}")
        console.print()

    if timeline:
        total = sum(timeline.values())
        console.print(f"[dim]Timeline: {total:.1f}s total — " + ", ".join(f"{k}={v:.2f}s" for k, v in timeline.items()) + "[/dim]")

    if decision == "PASS":
        return 0
    if decision == "PASS_WITH_WARNINGS":
        return 0
    if decision == "BLOCK":
        return 1
    return 3


@app.command()
def init(
    force: bool = typer.Option(False, "--force", help="Overwrite existing qgate.yaml"),
) -> None:
    """Initialize Q-GATE AI in the current directory."""
    target = Path.cwd() / "qgate.yaml"
    if target.exists() and not force:
        console.print("[yellow]qgate.yaml already exists. Use --force to overwrite.[/yellow]")
        raise typer.Exit(0)

    # Copy default from package root if available
    package_default = Path(__file__).resolve().parents[2] / "qgate.yaml"
    if package_default.exists():
        target.write_text(package_default.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        target.write_text(
            "project:\n  name: my-project\nquality_gate:\n  minimum_quality_score: 80\n  maximum_risk_score: 60\n",
            encoding="utf-8",
        )
    Path(".qgate").mkdir(exist_ok=True)
    console.print(f"[green]✓[/green] Created {target}")
    console.print("[dim]Edit qgate.yaml to customize policies.[/dim]")


@app.command()
def check(
    base: str = typer.Option("main", "--base", "-b", help="Base ref (branch or commit)"),
    head: str = typer.Option("HEAD", "--head", "-h", help="Head ref (branch or commit)"),
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Repository path (default: cwd)"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to qgate.yaml"),
) -> None:
    """Run the quality gate analysis (main entry point for CI/pre-push)."""
    _print_banner()
    repo = str(Path(path or Path.cwd()).resolve())

    try:
        from graphs.main_graph import run_quality_gate

        with console.status("[cyan]Analyzing change…[/cyan]"):
            state = run_quality_gate(
                repository_path=repo,
                base=base,
                head=head,
                config_path=config,
            )
        code = _print_result(dict(state))
        raise typer.Exit(code)
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(3) from e


@app.command()
def analyze(
    base: str = typer.Option("main", "--base", "-b"),
    head: str = typer.Option("HEAD", "--head", "-h"),
    path: Optional[str] = typer.Option(None, "--path", "-p"),
) -> None:
    """Alias for `check` — analyze a change without blocking semantics emphasis."""
    check(base=base, head=head, path=path, config=None)


@app.command()
def report(
    path: Optional[str] = typer.Option(None, "--path", "-p"),
) -> None:
    """Show location of last generated reports."""
    out = Path(path or Path.cwd()) / ".qgate" / "reports"
    if not out.exists():
        console.print("[yellow]No reports found. Run `qgate check` first.[/yellow]")
        raise typer.Exit(0)
    for f in sorted(out.glob("qgate-report.*")):
        console.print(f"  {f}")




@app.command()
def suppress(
    fingerprint: str = typer.Argument(..., help="Finding fingerprint to mark false positive"),
    path: Optional[str] = typer.Option(None, "--path", "-p"),
    status: str = typer.Option("false_positive", "--status"),
) -> None:
    """Mark a finding as false_positive or ignored (remembered by quality memory)."""
    from core.memory.store import get_memory_store, reset_memory_store
    from core.policies.config import load_config

    reset_memory_store()
    cfg = load_config()
    conf = cfg.model_dump()
    if cfg.raw.get("memory"):
        conf["memory"] = cfg.raw["memory"]
    store = get_memory_store(conf)
    if not store:
        console.print("[red]Memory is disabled[/red]")
        raise typer.Exit(2)
    repo = str(Path(path or Path.cwd()).resolve())
    ok = store.mark_finding_status(repo, fingerprint, status)
    if ok:
        console.print(f"[green]✓[/green] Marked {fingerprint[:12]}… as {status}")
    else:
        console.print("[yellow]Finding not found in memory[/yellow]")
        raise typer.Exit(1)


@app.command("memory-stats")
def memory_stats(
    path: Optional[str] = typer.Option(None, "--path", "-p"),
) -> None:
    """Show quality memory summary for the repository."""
    from core.memory.store import get_memory_store, reset_memory_store
    from core.policies.config import load_config

    reset_memory_store()
    cfg = load_config()
    conf = cfg.model_dump()
    if cfg.raw.get("memory"):
        conf["memory"] = cfg.raw["memory"]
    store = get_memory_store(conf)
    if not store:
        console.print("[yellow]Memory disabled[/yellow]")
        raise typer.Exit(0)
    repo = str(Path(path or Path.cwd()).resolve())
    ctx = store.get_historical_context(repo)
    console.print(f"Analyses: {ctx.get('analysis_count', 0)}")
    console.print(f"Block rate: {ctx.get('failure_rate', 0):.0%}")
    console.print(f"Avg risk: {ctx.get('avg_risk', 0):.1f}")
    console.print(f"Flaky tests: {len(ctx.get('flaky_tests') or [])}")
    console.print(f"Suppressed findings: {len(ctx.get('suppressed_findings') or [])}")


@app.command()
def version() -> None:
    """Show version."""
    console.print("Q-GATE AI v0.1.0 (Phase 1 — Foundation)")


if __name__ == "__main__":
    app()
