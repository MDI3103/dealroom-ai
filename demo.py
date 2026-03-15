"""
demo.py — DealRoom AI Demo Script
Tests 3 scenarios:
1. Grab (GRAB) — public company, should produce full data
2. Notion — private company, fallback path
3. "INVALID__COMPANY__XYZ_99" — should trigger graceful degradation
"""

import asyncio
import sys
import json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

sys.path.insert(0, str(Path(__file__).parent))
from orchestrator.orchestrator_agent import OrchestratorAgent

console = Console()


def print_trace(entry: dict):
    status = entry.get("status", "info")
    agent = entry.get("agent", "?")
    step = entry.get("step", "")
    detail = entry.get("detail", "")[:80]

    color = {
        "info": "cyan", "success": "green", "warning": "yellow",
        "error": "red", "tool_call": "blue",
    }.get(status, "white")

    console.print(f"  [{color}]{agent:20s}[/] {step}: {detail}")


async def run_demo(company: str, label: str):
    console.print(Panel(f"[bold cyan]{label}[/]\nAnalysing: [yellow]{company}[/]",
                        box=box.DOUBLE_EDGE))

    orchestrator = OrchestratorAgent(trace_callback=print_trace)

    try:
        result = await orchestrator.analyse(company)
    except Exception as e:
        console.print(f"[red]CRITICAL ERROR: {e}[/]")
        return

    report = result.get("report", {})
    raw = result.get("raw_data", {})

    # ── Summary Table ─────────────────────────────────
    table = Table(title=f"Results: {company}", box=box.ROUNDED, border_style="cyan")
    table.add_column("Field", style="cyan", width=22)
    table.add_column("Value", style="white")

    verdict = report.get("investment_verdict", "N/A")
    verdict_color = {"BUY": "green", "HOLD": "yellow", "AVOID": "red"}.get(verdict, "white")

    table.add_row("Verdict", f"[{verdict_color}]{verdict}[/]")
    table.add_row("Confidence", f"{report.get('confidence_score', 0)}%")
    table.add_row("Duration", f"{result.get('duration_seconds', 0)}s")
    table.add_row("Agents OK", str(result.get("agents_succeeded", 0)) + "/4")

    fin = raw.get("financial", {})
    table.add_row("Market Cap", fin.get("market_cap", "N/A"))
    table.add_row("Revenue TTM", fin.get("revenue_ttm", "N/A"))
    table.add_row("Risk Level", raw.get("risk", {}).get("overall_risk_level", "N/A"))
    table.add_row("Sentiment", raw.get("sentiment", {}).get("overall_sentiment", "N/A"))

    console.print(table)

    # ── A2A messages ──────────────────────────────────
    a2a = result.get("a2a_messages", [])
    if a2a:
        console.print(f"\n[purple]A2A Messages ({len(a2a)}):[/]")
        for msg in a2a[:5]:
            console.print(
                f"  [purple]→ {msg['sender']} → {msg['recipient']} [{msg['message_type']}][/] "
                f"{json.dumps(msg.get('payload', {}))[:100]}"
            )

    # ── Executive Summary ─────────────────────────────
    console.print(f"\n[bold]Executive Summary:[/]")
    console.print(report.get("executive_summary", "N/A"))
    console.print("\n" + "─" * 80 + "\n")


async def main():
    console.print(Panel(
        "[bold cyan]🏦 DealRoom AI — Demo Run[/]\n"
        "Tests 3 scenarios: Public Company · Private Company · Graceful Failure",
        box=box.HEAVY
    ))

    scenarios = [
        ("Grab", "Scenario 1: Public Company (GRAB — NASDAQ listed)"),
        ("Notion", "Scenario 2: Private Company (Notion — no ticker)"),
        ("INVALID_COMPANY_XYZ_99999", "Scenario 3: Unknown company (graceful degradation test)"),
    ]

    for company, label in scenarios:
        await run_demo(company, label)
        await asyncio.sleep(1)  # Brief pause between runs

    console.print(Panel("[bold green]✅ Demo complete![/]", box=box.ROUNDED))


if __name__ == "__main__":
    asyncio.run(main())
