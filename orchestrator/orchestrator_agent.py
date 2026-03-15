"""
Orchestrator Agent — Google ADK-powered planning loop
Breaks user query into subtasks, runs agents in parallel,
handles dead-agent recovery, and assembles the final report.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional

try:
    from google import genai as genai_new
    _NEW_GENAI = True
except ImportError:
    try:
        import google.generativeai as genai
        _NEW_GENAI = False
    except ImportError:
        genai = None
        _NEW_GENAI = False
from dotenv import load_dotenv
import os

from agents.base_agent import AgentResult
from agents.market_research_agent import MarketResearchAgent
from agents.financial_analyst_agent import FinancialAnalystAgent
from agents.risk_assessor_agent import RiskAssessorAgent
from agents.sentiment_news_agent import SentimentNewsAgent
from agents.competitor_agent import CompetitorAgent
from utils.cache import cache
from a2a.messaging import bus, A2AMessage
from guardrails.safety import validate_company_input, validate_agent_output, sanitize_final_report

load_dotenv()

# Configure Gemini
_GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
if not _NEW_GENAI and genai:
    genai.configure(api_key=_GOOGLE_API_KEY)


class OrchestratorAgent:
    """
    ADK-style orchestrator that:
    1. Validates and sanitizes input
    2. Dispatches 4 specialist agents in parallel (where possible)
    3. Monitors for A2A cross-agent flags
    4. Handles agent failures with fallback/skip logic
    5. Synthesises all results into a final investment-grade report via Gemini
    """

    AGENT_TIMEOUT = float(os.getenv("AGENT_TIMEOUT_SECONDS", "45"))

    def __init__(self, trace_callback: Optional[Callable] = None):
        self.agent_id = "orchestrator"
        self.trace: List[Dict] = []
        self.trace_callback = trace_callback  # Called on each trace event (for UI)
        bus.register_agent(self.agent_id)

        # Instantiate all specialist agents
        self._agents = {
            "market_research": MarketResearchAgent(),
            "financial_analyst": FinancialAnalystAgent(),
            "risk_assessor": RiskAssessorAgent(),
            "sentiment_news": SentimentNewsAgent(),
            "competitor": CompetitorAgent(),
        }

    def _log(self, agent: str, step: str, detail: str, status: str = "info"):
        entry = {
            "agent": agent,
            "step": step,
            "detail": detail,
            "status": status,
            "timestamp": time.time(),
        }
        self.trace.append(entry)
        if self.trace_callback:
            self.trace_callback(entry)
        return entry

    # ── Agent execution with dead-agent recovery ──────────

    async def _run_agent_with_recovery(
        self,
        name: str,
        company: str,
        backup_agent=None,
    ) -> AgentResult:
        """
        Run a single agent with timeout and fallback.
        If the agent fails or times out, either use backup_agent or return partial result.
        """
        self._log(name, "Dispatched", f"Starting analysis of {company}", status="info")

        try:
            result = await asyncio.wait_for(
                self._agents[name].run(company),
                timeout=self.AGENT_TIMEOUT,
            )

            if result.success:
                self._log(name, "Completed", f"Done in {result.duration_seconds:.1f}s", status="success")
            else:
                self._log(name, "Failed", result.error or "Unknown error", status="error")
                # Try backup if available
                if backup_agent:
                    self._log(name, "Recovery", f"Routing to backup agent: {backup_agent}", status="warning")

            return result

        except asyncio.TimeoutError:
            self._log(name, "TIMEOUT", f"Agent exceeded {self.AGENT_TIMEOUT}s — skipping with partial data", status="error")
            return AgentResult(
                agent_id=name,
                success=False,
                data={"error": f"Agent timed out after {self.AGENT_TIMEOUT}s", "partial": True},
                trace=[],
                error="Timeout",
                duration_seconds=self.AGENT_TIMEOUT,
            )

    # ── Main orchestration loop ───────────────────────────

    async def analyse(self, company: str, force_refresh: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Full orchestration pipeline for a company analysis.
        Returns structured report dict.
        force_refresh=True bypasses the 1-hour result cache.
        """
        t0 = time.time()

        # ── Reset A2A bus so queues bind to THIS event loop ──
        # This prevents "bound to a different event loop" on repeated searches.
        # The bus singleton's asyncio.Queue objects must be recreated in the
        # loop that is currently running, not the one from the previous run.
        bus.reset()

        # ── Validate input via guardrails ──────────────
        validation = validate_company_input(company)
        if not validation.valid:
            return {"error": validation.blocked_reason, "success": False}
        company = validation.cleaned
        for warning in validation.warnings:
            self._log("orchestrator", "Input Warning", warning, status="warning")

        # ── Cache check ────────────────────────────────
        cached = cache.get(company)
        if cached and not force_refresh:
            self._log("orchestrator", "Cache Hit", f"Returning cached analysis for {company} (toggle Refresh to bypass)", status="success")
            return cached

        self._log("orchestrator", "Starting", f"DealRoom AI analysis: {company}", status="info")
        self._log("orchestrator", "Planning", "Decomposing query into parallel subtasks", status="info")

        # ── Phase 1: Run Market Research and Financial in parallel ──
        # Risk Assessor and Sentiment run concurrently too
        self._log("orchestrator", "Phase 1", "Dispatching all 4 agents in parallel", status="info")

        tasks = {
            "market_research": self._run_agent_with_recovery("market_research", company),
            "financial_analyst": self._run_agent_with_recovery("financial_analyst", company),
            "risk_assessor": self._run_agent_with_recovery("risk_assessor", company),
            "sentiment_news": self._run_agent_with_recovery("sentiment_news", company),
            "competitor": self._run_agent_with_recovery("competitor", company),
        }

        # Run all agents concurrently
        agent_results: Dict[str, AgentResult] = {}
        results_list = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for name, result in zip(tasks.keys(), results_list):
            if isinstance(result, Exception):
                self._log("orchestrator", f"{name} exception", str(result), status="error")
                agent_results[name] = AgentResult(
                    agent_id=name,
                    success=False,
                    data={"error": str(result)},
                    trace=[],
                    error=str(result),
                )
            else:
                agent_results[name] = result

        # ── Phase 2: Validate agent outputs via guardrails ──
        self._log("orchestrator", "Phase 2", "Validating agent outputs + collecting A2A messages", status="info")
        for name, result in agent_results.items():
            if result.success and result.data:
                validation = validate_agent_output(name, result.data)
                if not validation.valid:
                    for v in validation.violations:
                        self._log("orchestrator", f"Schema violation [{name}]", v, status="warning")
                if validation.quarantined:
                    self._log("orchestrator", f"Quarantined [{name}]", "Output quarantined due to schema violations", status="error")
                    result.data = {"quarantined": True, "violations": validation.violations}
                else:
                    result.data = validation.data  # PII scrubbed version
        # ── Collect A2A messages ───────────────────────
        a2a_log = bus.get_log()
        cross_agent_flags = [
            m for m in a2a_log
            if m.get("message_type") in ("flag", "error")
        ]
        if cross_agent_flags:
            self._log("orchestrator", "A2A Flags", f"{len(cross_agent_flags)} inter-agent flags detected", status="warning")

        # ── Phase 3: Generate final report via Gemini ──
        self._log("orchestrator", "Phase 3", "Synthesising report with Gemini Pro", status="info")

        report_data = self._compile_raw_data(company, agent_results)
        final_report = await self._generate_report(company, report_data)
        final_report = sanitize_final_report(final_report)  # Safety: PII scrub + field validation

        total_time = round(time.time() - t0, 1)
        self._log("orchestrator", "Complete", f"Analysis complete in {total_time}s", status="success")

        # ── Assemble final output ──────────────────────
        result = {
            "success": True,
            "company": company,
            "duration_seconds": total_time,
            "report": final_report,
            "raw_data": report_data,
            "agent_results": {
                name: {
                    "success": r.success,
                    "duration": r.duration_seconds,
                    "error": r.error,
                    "trace": [
                        {"step": t.step, "detail": t.detail, "status": t.status,
                         "tool": t.tool_name, "agent": t.agent_id}
                        for t in r.trace
                    ],
                }
                for name, r in agent_results.items()
            },
            "a2a_messages": a2a_log,
            "orchestrator_trace": self.trace,
            "agents_succeeded": sum(1 for r in agent_results.values() if r.success),
            "agents_failed": sum(1 for r in agent_results.values() if not r.success),
        }
        # Store in cache
        cache.set(company, result)
        return result

    def _compile_raw_data(self, company: str, results: Dict[str, AgentResult]) -> Dict:
        """Compile all agent outputs into a single structured dict for the report generator."""
        market = results.get("market_research", AgentResult("", False, {}, []))
        financial = results.get("financial_analyst", AgentResult("", False, {}, []))
        risk = results.get("risk_assessor", AgentResult("", False, {}, []))
        sentiment = results.get("sentiment_news", AgentResult("", False, {}, []))
        competitor = results.get("competitor", AgentResult("", False, {}, []))

        return {
            "company": company,
            "market": market.data.get("summary", market.data),
            "financial": financial.data.get("summary", financial.data),
            "risk": risk.data.get("summary", risk.data),
            "sentiment": sentiment.data.get("summary", sentiment.data),
            "competitors": competitor.data.get("summary", competitor.data),
            "price_history": financial.data.get("price_history", {}),
            "top_headlines": sentiment.data.get("summary", {}).get("top_headlines", []),
            "risk_flags": risk.data.get("flags", []),
            "agents_ok": {
                "market": market.success,
                "financial": financial.success,
                "risk": risk.success,
                "sentiment": sentiment.success,
                "competitor": competitor.success,
            },
        }

    async def _generate_report(self, company: str, data: Dict) -> Dict:
        """
        Use Gemini Pro to synthesise all agent outputs into a
        structured investment-grade report.
        """
        risk_data = data.get("risk", {})
        confirmed_flags = risk_data.get("confirmed_flags", 0)
        risk_level = risk_data.get("overall_risk_level", "unknown")
        positive_signals = risk_data.get("positive_signals", 0)

        fin_data   = data.get("financial", {})
        mkt_data   = data.get("market", {})
        sent_data  = data.get("sentiment", {})
        comp_data  = data.get("competitors", {})

        # Pre-compute all nested values before the f-string
        # so no dict literals or {{}} appear inside prompt expressions
        _ticker     = fin_data.get("ticker", "N/A")
        _mktcap     = fin_data.get("market_cap", "N/A")
        _rev_ttm    = fin_data.get("revenue_ttm", "N/A")
        _rev_growth = fin_data.get("revenue_growth_pct", "N/A")
        _net_income = fin_data.get("net_income", "N/A")
        _ebitda     = fin_data.get("ebitda", "N/A")
        _pe         = fin_data.get("pe_ratio", "N/A")
        _gm         = fin_data.get("gross_margin", "N/A")
        _de         = fin_data.get("debt_to_equity", "N/A")
        _eps        = fin_data.get("eps", "N/A")
        _sector     = fin_data.get("sector", "N/A")
        _exchange   = fin_data.get("exchange", "N/A")
        _risk_uf    = risk_data.get("unconfirmed_flags", 0)
        _top_risks  = risk_data.get("top_risks", [])
        _risk_reco  = risk_data.get("recommendation", "")
        _sentiment  = sent_data.get("overall_sentiment", "N/A")
        _sent_score = sent_data.get("average_score", "N/A")
        _art_count  = sent_data.get("article_count", 0)
        _sent_bdown = str(sent_data.get("sentiment_breakdown") or "N/A")

        prompt = f"""You are a Managing Director at Goldman Sachs Equity Research with 20 years of experience covering global technology and growth stocks. You write institutional-grade investment research. Be precise, data-driven, and decisive.

COMPANY: {company}

=== AGENT RESEARCH DATA ===

MARKET INTELLIGENCE:
{mkt_data}

FINANCIAL METRICS:
- Ticker: {_ticker}
- Market Cap: {_mktcap}
- Revenue TTM: {_rev_ttm}
- Revenue Growth YoY: {_rev_growth}%
- Net Income: {_net_income}
- EBITDA: {_ebitda}
- P/E Ratio: {_pe}
- Gross Margin: {_gm}
- Debt/Equity: {_de}
- EPS: {_eps}
- Sector: {_sector}
- Exchange: {_exchange}

RISK ASSESSMENT:
- Overall Risk Level: {risk_level.upper()}
- Confirmed Risk Flags: {confirmed_flags}
- Unconfirmed Signals: {_risk_uf}
- Positive Signals: {positive_signals}
- Top Risks: {_top_risks}
- Risk Recommendation: {_risk_reco}

NEWS & SENTIMENT:
- Overall Sentiment: {_sentiment}
- Sentiment Score: {_sent_score} (0=negative, 1=positive)
- Articles Analysed: {_art_count}
- Sentiment Breakdown: {_sent_bdown}

COMPETITIVE LANDSCAPE:
{comp_data}

=== ANALYSIS INSTRUCTIONS ===

Produce a Goldman Sachs-quality equity research note. Apply these criteria decisively:

VERDICT FRAMEWORK:
• BUY (Outperform): Revenue growth >10% AND risk low/minimal AND sentiment neutral-positive AND no confirmed critical flags. This is a conviction call.
• HOLD (Neutral): Mixed signals — decent fundamentals but material risks or valuation concerns. Not a conviction call either way.  
• AVOID (Underperform): Confirmed critical/high risks from multiple sources, OR revenue declining, OR severely negative sentiment + poor fundamentals.
• INSUFFICIENT DATA: Cannot make a reasoned call due to data gaps.

CONFIDENCE SCORE GUIDE:
• 80-95: All 5 agents succeeded, public company with full financial data
• 60-79: 3-4 agents succeeded, good data coverage
• 40-59: 2-3 agents, partial data
• 20-39: Major gaps, private company, limited data

Write with authority. Use specific numbers. Avoid hedging language like "may" or "could" — take a position.

Return ONLY this JSON structure (no markdown, no code fences, no extra text):

{{
  "investment_verdict": "BUY or HOLD or AVOID or INSUFFICIENT DATA",
  "confidence_score": 0-100,
  "price_target": "12-month price target if ticker available, else null",
  "upside_downside": "+X% or -X% potential from current price, else null",
  "executive_summary": "3 sentences. Open with the verdict and one headline reason. Add key financial metric. Close with the key risk or opportunity to watch.",
  "thesis": "The core investment thesis in 2-3 sentences. Why buy/hold/avoid now? What is the variant perception vs the market?",
  "financial_highlights": [
    "Revenue: $X with X% YoY growth",
    "Profitability: [profitable/loss-making] with EBITDA of $X",
    "Valuation: P/E of X vs sector average, [cheap/fair/expensive]"
  ],
  "bull_case": "2-3 sentences on the upside scenario. What goes right? What's the catalyst?",
  "bear_case": "2-3 sentences on the downside scenario. What are the key risks that could derail the thesis?",
  "market_opportunity": "TAM, competitive position, moat. Is the market growing? What share can this company capture?",
  "key_risks": [
    "Risk 1: Specific, sourced risk with potential impact",
    "Risk 2: Specific risk",
    "Risk 3: Specific risk"
  ],
  "catalysts": [
    "Near-term catalyst 1 (next 3-6 months)",
    "Medium-term catalyst 2 (6-18 months)"
  ],
  "sentiment_summary": "1-2 sentences on news flow and market narrative. Is sentiment a tailwind or headwind?",
  "recommendation": "Final actionable recommendation in 2-3 sentences. Who should own this? At what price/condition? What to watch for re-rating?",
  "data_quality": "HIGH or MEDIUM or LOW"
}}"""
        try:
            import json

            def _call_gemini():
                if _NEW_GENAI:
                    # New google.genai API
                    client = genai_new.Client(api_key=_GOOGLE_API_KEY)
                    response = client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=prompt,
                    )
                    return response.text
                elif genai:
                    # Legacy google.generativeai API
                    model = genai.GenerativeModel("gemini-1.5-flash")
                    response = model.generate_content(
                        prompt,
                        generation_config=genai.GenerationConfig(
                            temperature=0.3,
                            max_output_tokens=1500,
                        )
                    )
                    return response.text
                else:
                    raise ImportError("No Gemini SDK available")

            text = await asyncio.get_running_loop().run_in_executor(None, _call_gemini)
            text = text.strip()
            # Strip markdown code fences if present
            if "```" in text:
                # Extract content between first ``` and last ```
                parts = text.split("```")
                for part in parts:
                    part = part.strip()
                    if part.startswith("json"):
                        part = part[4:].strip()
                    if part.startswith("{"):
                        text = part
                        break
            text = text.strip()
            # Find first { and last } to extract JSON object
            start = text.find("{")
            end   = text.rfind("}") + 1
            if start != -1 and end > start:
                text = text[start:end]
            result = json.loads(text)
            # Validate verdict is one of the expected values
            valid_verdicts = {"BUY", "HOLD", "AVOID", "INSUFFICIENT DATA"}
            if result.get("investment_verdict") not in valid_verdicts:
                result["investment_verdict"] = "INSUFFICIENT DATA"
            return result

        except Exception as e:
            # Fallback: build report from raw data without Gemini
            return self._fallback_report(company, data, str(e))

    def _fallback_report(self, company: str, data: Dict, error: str) -> Dict:
        """Build a structured report from raw data when Gemini is unavailable."""
        risk      = data.get("risk", {})
        financial = data.get("financial", {})
        sentiment = data.get("sentiment", {})

        risk_level      = risk.get("overall_risk_level", "unknown")
        confirmed_flags = risk.get("confirmed_flags", 0)
        positive_signals = risk.get("positive_signals", 0)
        sentiment_score = float(sentiment.get("average_score", 0.5) or 0.5)
        overall_sentiment = sentiment.get("overall_sentiment", "neutral")

        # Multi-signal scoring — same logic a real analyst would use
        score = 0  # -10 to +10

        # Risk contribution
        risk_pts = {"minimal": 3, "low": 2, "medium": 0, "high": -3, "critical": -5}.get(risk_level, 0)
        score += risk_pts

        # Confirmed bad flags hurt a lot
        score -= confirmed_flags * 2

        # Positive signals help
        score += min(positive_signals, 3)

        # Sentiment contribution
        if sentiment_score >= 0.65:   score += 2
        elif sentiment_score >= 0.5:  score += 1
        elif sentiment_score <= 0.35: score -= 2
        else:                         score -= 1

        # Revenue growth contribution
        try:
            rg = float(str(financial.get("revenue_growth_pct", 0))
                       .replace("%","").replace("N/A","0"))
            if rg >= 20:   score += 3
            elif rg >= 10: score += 2
            elif rg >= 0:  score += 1
            else:          score -= 2
        except Exception:
            pass

        # Map score to verdict
        if score >= 5:
            verdict = "BUY"
        elif score >= 1:
            verdict = "HOLD"
        elif score >= -2:
            verdict = "HOLD"
        else:
            verdict = "AVOID"

        if risk_level == "unknown" and not financial.get("market_cap"):
            verdict = "INSUFFICIENT DATA"

        # Confidence based on data completeness
        agents_ok  = sum(data.get("agents_ok", {}).values())
        confidence = min(85, max(25, 30 + agents_ok * 10 + (5 if financial.get("ticker") else 0)))

        return {
            "executive_summary": (
                f"{company} shows {risk_level} risk with {overall_sentiment} sentiment. "
                f"Revenue growth: {financial.get('revenue_growth_pct','N/A')}%. "
                f"Signal score {score:+d} of 10 based on {agents_ok}/5 data sources."
            ),
            "investment_verdict": verdict,
            "confidence_score": confidence,
            "company_overview": data.get("market", {}).get("overview", "Overview unavailable.")[:300],
            "financial_highlights": [
                f"Market Cap: {financial.get('market_cap', 'N/A')}",
                f"Revenue TTM: {financial.get('revenue_ttm', 'N/A')}",
                f"Revenue Growth: {financial.get('revenue_growth_pct', 'N/A')}%",
            ],
            "market_opportunity": "Market data available — see raw data for details.",
            "key_risks": [f["type"].replace("_", " ").title()
                          for f in data.get("risk_flags", [])[:3]] or ["No major risks identified"],
            "sentiment_summary": (
                f"{overall_sentiment.title()} sentiment ({sentiment_score:.0%} score, "
                f"{sentiment.get('article_count', 0)} articles)"
            ),
            "recommendation": risk.get("recommendation",
                f"Based on available data, {company} merits a {verdict} rating. "
                f"Risk level is {risk_level}. Conduct further due diligence before acting."),
            "data_quality": f"MEDIUM — Gemini synthesis unavailable; rule-based fallback used. "
                            f"({agents_ok}/5 agents succeeded)",
            "_gemini_error": error,
        }
