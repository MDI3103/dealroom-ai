"""
Agent 5 — Sentiment & News Agent (Improved)
Now uses Gemini for accurate per-article sentiment scoring.
Falls back to rule-based if Gemini unavailable.
"""
from __future__ import annotations
import asyncio
import os
from statistics import mean
from typing import Any, Dict, List

from agents.base_agent import BaseAgent
from mcp_tools.tools import get_news, analyze_sentiment, get_reddit_mentions, web_search


def gemini_sentiment(text: str) -> Dict:
    """Use Gemini to score sentiment — much more accurate than rule-based."""
    try:
        api_key = os.getenv("GOOGLE_API_KEY", "")
        if not api_key:
            return analyze_sentiment(text)

        try:
            from google import genai as genai_new
            client = genai_new.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=f"""Rate the sentiment of this financial news headline.
Reply with ONLY a JSON object, nothing else:
{{"label": "positive" or "neutral" or "negative", "score": 0.0-1.0, "reason": "brief reason"}}

Headline: {text[:200]}""",
            )
            import json, re
            raw = response.text.strip()
            raw = re.sub(r'```json|```', '', raw).strip()
            result = json.loads(raw)
            return {
                "label": result.get("label", "neutral"),
                "score": float(result.get("score", 0.5)),
                "pos_signals": 1 if result.get("label") == "positive" else 0,
                "neg_signals": 1 if result.get("label") == "negative" else 0,
                "reason": result.get("reason", ""),
            }
        except Exception:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                response = model.generate_content(
                    f'Rate sentiment as JSON {{label, score 0-1}}: {text[:200]}'
                )
                import json, re
                raw = re.sub(r'```json|```', '', response.text.strip()).strip()
                result = json.loads(raw)
                return {"label": result.get("label","neutral"), "score": float(result.get("score",0.5)),
                        "pos_signals": 0, "neg_signals": 0}
            except Exception:
                return analyze_sentiment(text)
    except Exception:
        return analyze_sentiment(text)


class SentimentNewsAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_id="sentiment_news", timeout=45.0, max_retries=3)
        self._use_gemini_sentiment = bool(os.getenv("GOOGLE_API_KEY"))

    async def _execute(self, company: str, **kwargs) -> Dict[str, Any]:
        self._log("Planning", f"Starting sentiment & news analysis for: {company}")
        results: Dict[str, Any] = {}

        # Step 1: Fetch news
        self._log("Step 1/4", "Fetching recent news (NewsAPI → Google RSS fallback)")
        articles = await self._run_tool_with_retry(
            tool_fn=get_news,
            tool_name="get_news",
            params_description=f"company={company}",
            fallback_fn=lambda: self._emergency_fallback(company),
            tool_args=(company, 10),
        )
        results["raw_articles"] = articles or []

        # Step 2: Sentiment analysis — Gemini if available, else rule-based
        method = "Gemini AI" if self._use_gemini_sentiment else "rule-based"
        self._log("Step 2/4", f"Scoring sentiment per article ({method})")

        enriched = []
        for article in results["raw_articles"][:10]:
            text = f"{article.get('title', '')} {article.get('description', '')}"
            if self._use_gemini_sentiment:
                sentiment = await asyncio.get_running_loop().run_in_executor(
                    None, gemini_sentiment, text
                )
            else:
                sentiment = await asyncio.get_running_loop().run_in_executor(
                    None, analyze_sentiment, text
                )
            article["sentiment"] = sentiment
            enriched.append(article)
        results["articles"] = enriched

        # Step 3: Reddit
        self._log("Step 3/4", "Scanning Reddit for community sentiment")
        reddit = await self._run_tool_with_retry(
            tool_fn=get_reddit_mentions,
            tool_name="reddit_mentions",
            params_description=f"company={company}",
            fallback_fn=lambda: [],
            tool_args=(company,),
        )
        results["reddit_mentions"] = reddit or []

        # Step 4: Reputation search
        self._log("Step 4/4", "Running targeted reputation search")
        reputation = await self._run_tool_with_retry(
            tool_fn=web_search,
            tool_name="web_search_reputation",
            params_description=f"{company} public perception brand",
            fallback_fn=lambda: [],
            tool_args=(f"{company} public perception brand reputation 2024 2025",),
            tool_kwargs={"max_results": 4},
        )
        results["reputation_search"] = reputation or []

        msg = await self.check_inbox()
        if msg:
            self._log(f"A2A from {msg.sender}", str(msg.payload)[:100], status="info")
            # If orchestrator sends "viral_news_check", do extra scan
            if msg.payload.get("check_type") == "viral":
                extra = await self._run_tool_with_retry(
                    tool_fn=web_search, tool_name="viral_news_check",
                    params_description="viral news check",
                    fallback_fn=lambda: [],
                    tool_args=(f"{company} viral trending news today",),
                    tool_kwargs={"max_results": 3},
                )
                results["viral_news"] = extra or []

        results["summary"] = self._synthesise(company, results)

        # A2A: Send low sentiment alert to orchestrator
        summary = results["summary"]
        if summary.get("average_score", 0.5) < 0.35:
            await self.send_flag(
                recipient="orchestrator",
                flag_type="negative_sentiment_spike",
                detail=f"Average sentiment score {summary['average_score']} — overwhelmingly negative coverage",
                severity="high",
            )
            self._log("A2A → orchestrator", "Negative sentiment spike flagged", status="warning")

        self._log("Complete", f"Sentiment done for {company}", status="success")
        return results

    def _emergency_fallback(self, company: str) -> List[Dict]:
        self._warn("NewsAPI + RSS failed", "Using web search emergency fallback")
        results = web_search(f"{company} news latest 2025", max_results=5)
        return [{"title": r.get("title",""), "description": r.get("content","")[:200],
                 "source": "web_search_fallback", "published_at": "recent",
                 "url": r.get("url",""), "sentiment": None} for r in results]

    def _synthesise(self, company: str, data: Dict) -> Dict:
        articles = data.get("articles", [])
        reddit = data.get("reddit_mentions", [])
        scores, labels = [], []

        for item in articles + reddit:
            s = item.get("sentiment")
            if s and isinstance(s.get("score"), (int, float)):
                scores.append(s["score"])
                labels.append(s.get("label", "neutral"))

        avg = mean(scores) if scores else 0.5
        pos = labels.count("positive")
        neg = labels.count("negative")
        neu = labels.count("neutral")

        overall = "Positive" if avg > 0.6 else ("Negative" if avg < 0.4 else "Neutral")
        emoji = {"Positive": "📈", "Negative": "📉", "Neutral": "➡️"}[overall]

        return {
            "company": company,
            "overall_sentiment": overall,
            "sentiment_emoji": emoji,
            "average_score": round(avg, 2),
            "article_count": len(articles),
            "positive_articles": pos,
            "negative_articles": neg,
            "neutral_articles": neu,
            "reddit_mention_count": len(reddit),
            "top_headlines": [
                {"title": a.get("title","")[:100], "source": a.get("source",""),
                 "sentiment_label": a.get("sentiment",{}).get("label","neutral") if a.get("sentiment") else "neutral",
                 "sentiment_reason": a.get("sentiment",{}).get("reason","") if a.get("sentiment") else "",
                 "url": a.get("url","")}
                for a in articles[:6]
            ],
            "sentiment_breakdown": {"positive": pos, "negative": neg, "neutral": neu},
        }
