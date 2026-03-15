"""
main.py — DealRoom AI Entry Point
Unified CLI for all run modes.

Usage:
  python main.py ui        → Launch Streamlit dashboard (default)
  python main.py api       → Launch A2A FastAPI server
  python main.py demo      → Run 3-scenario demo in terminal
  python main.py analyse "Grab"  → Single company analysis in terminal
  python main.py check     → Check API keys and dependencies
"""

import sys
import os
import asyncio
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))


def check_dependencies():
    """Check all required packages and API keys are present."""
    from rich.console import Console
    from rich.table import Table
    from rich import box

    console = Console()
    console.print("\n[bold cyan]🏦 DealRoom AI — Dependency Check[/]\n")

    # Check packages
    packages = [
        ("google-adk", "google.adk"),
        ("google-generativeai", "google.generativeai"),
        ("yfinance", "yfinance"),
        ("streamlit", "streamlit"),
        ("fastapi", "fastapi"),
        ("tenacity", "tenacity"),
        ("feedparser", "feedparser"),
        ("wikipedia", "wikipedia"),
        ("rich", "rich"),
        ("tavily-python", "tavily"),
        ("newsapi-python", "newsapi"),
    ]

    pkg_table = Table(title="Package Status", box=box.ROUNDED, border_style="cyan")
    pkg_table.add_column("Package", style="cyan")
    pkg_table.add_column("Status")

    for name, import_name in packages:
        try:
            __import__(import_name)
            pkg_table.add_row(name, "[green]✅ installed[/]")
        except ImportError:
            pkg_table.add_row(name, "[red]❌ missing — run: pip install " + name + "[/]")

    console.print(pkg_table)

    # Check API keys
    from dotenv import load_dotenv
    load_dotenv()

    keys = [
        ("GOOGLE_API_KEY", True, "Required for Gemini report synthesis"),
        ("TAVILY_API_KEY", False, "Optional — falls back to DuckDuckGo"),
        ("NEWS_API_KEY", False, "Optional — falls back to Google News RSS"),
        ("REDDIT_CLIENT_ID", False, "Optional — falls back to web search"),
    ]

    key_table = Table(title="API Key Status", box=box.ROUNDED, border_style="cyan")
    key_table.add_column("Key", style="cyan")
    key_table.add_column("Required")
    key_table.add_column("Status")
    key_table.add_column("Notes", style="dim")

    all_required_ok = True
    for key, required, note in keys:
        val = os.getenv(key, "")
        present = bool(val and val != f"your_{key.lower()}_here")
        status = "[green]✅ set[/]" if present else ("[red]❌ missing[/]" if required else "[yellow]⚠ not set[/]")
        req_str = "[red]Yes[/]" if required else "No"
        if required and not present:
            all_required_ok = False
        key_table.add_row(key, req_str, status, note)

    console.print(key_table)

    if not all_required_ok:
        console.print("\n[red]⚠ Some required keys are missing. Copy .env.example to .env and fill in your keys.[/]")
        console.print("  [dim]cp .env.example .env[/]\n")
    else:
        console.print("\n[green]✅ All required keys are set. Ready to run![/]\n")


async def analyse_single(company: str):
    """Run a single company analysis and print the result."""
    from rich.console import Console
    from rich.panel import Panel
    from rich import box

    console = Console()

    def on_trace(entry):
        status = entry.get("status", "info")
        color = {"info": "cyan", "success": "green", "warning": "yellow", "error": "red", "tool_call": "blue"}.get(status, "white")
        agent = entry.get("agent", "?")
        step = entry.get("step", "")
        detail = entry.get("detail", "")[:100]
        console.print(f"  [{color}]{agent:22s}[/] {step}: {detail}")

    console.print(Panel(f"[bold cyan]Analysing: {company}[/]", box=box.ROUNDED))

    from orchestrator.orchestrator_agent import OrchestratorAgent
    orch = OrchestratorAgent(trace_callback=on_trace)
    result = await orch.analyse(company)

    report = result.get("report", {})
    raw = result.get("raw_data", {})

    verdict = report.get("investment_verdict", "N/A")
    color = {"BUY": "green", "HOLD": "yellow", "AVOID": "red"}.get(verdict, "white")

    console.print(Panel(
        f"[{color}]{verdict}[/] | Confidence: {report.get('confidence_score', 0)}% | "
        f"Duration: {result.get('duration_seconds', 0)}s | "
        f"Agents OK: {result.get('agents_succeeded', 0)}/4\n\n"
        f"[bold]Summary:[/] {report.get('executive_summary', 'N/A')}\n\n"
        f"[bold]Recommendation:[/] {report.get('recommendation', 'N/A')}",
        title=f"[cyan]{company} — DealRoom AI Report[/]",
        box=box.DOUBLE_EDGE,
    ))


def main():
    args = sys.argv[1:]
    mode = args[0] if args else "ui"

    if mode == "ui":
        print("Launching Streamlit dashboard...")
        os.execvp("streamlit", ["streamlit", "run", "frontend/app.py"])

    elif mode == "api":
        print("Starting A2A FastAPI server...")
        os.execvp("uvicorn", [
            "uvicorn", "a2a.server:app",
            "--host", "0.0.0.0",
            "--port", os.getenv("ORCHESTRATOR_PORT", "8000"),
            "--reload",
        ])

    elif mode == "demo":
        from demo import main as demo_main
        asyncio.run(demo_main())

    elif mode == "analyse" and len(args) >= 2:
        company = " ".join(args[1:])
        asyncio.run(analyse_single(company))

    elif mode == "check":
        check_dependencies()

    else:
        print(__doc__)


if __name__ == "__main__":
    main()
