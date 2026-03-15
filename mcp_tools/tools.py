"""
MCP Tools Registry
Each agent has its own isolated toolbox via MCP.
"""

from __future__ import annotations

import os
import re
import time
import asyncio
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()

# ── Optional dependency guards ─────────────────────────────
try:
    import feedparser
    _FEEDPARSER = True
except ImportError:
    _FEEDPARSER = False

try:
    import requests
    _REQUESTS = True
except ImportError:
    _REQUESTS = False

try:
    import wikipedia
    _WIKIPEDIA = True
except ImportError:
    _WIKIPEDIA = False

try:
    import yfinance as yf
    _YFINANCE = True
except ImportError:
    _YFINANCE = False

TAVILY_API_KEY  = os.getenv("TAVILY_API_KEY", "")
NEWS_API_KEY    = os.getenv("NEWS_API_KEY", "")
SERP_API_KEY    = os.getenv("SERP_API_KEY", "")   # optional — free at serpapi.com


# ══════════════════════════════════════════════════════════
# WEB SEARCH
# ══════════════════════════════════════════════════════════

def web_search(query: str, max_results: int = 5) -> List[Dict]:
    """
    Search the web. Tries Tavily → SerpAPI → DuckDuckGo in order.
    """
    if TAVILY_API_KEY:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=TAVILY_API_KEY)
            response = client.search(query=query, max_results=max_results)
            results = response.get("results", [])
            if results:
                return results
        except Exception:
            pass

    if SERP_API_KEY and _REQUESTS:
        try:
            import requests as req
            r = req.get("https://serpapi.com/search", params={
                "q": query, "api_key": SERP_API_KEY,
                "num": max_results, "engine": "google",
            }, timeout=10)
            data = r.json()
            return [
                {"title": item.get("title",""), "content": item.get("snippet",""), "url": item.get("link","")}
                for item in data.get("organic_results", [])[:max_results]
            ]
        except Exception:
            pass

    # Fallback: DuckDuckGo
    if _REQUESTS:
        try:
            import requests as req
            r = req.get("https://api.duckduckgo.com/", params={
                "q": query, "format": "json", "no_redirect": 1
            }, timeout=10)
            data = r.json()
            results = []
            if data.get("AbstractText"):
                results.append({
                    "title": data.get("Heading", query),
                    "content": data["AbstractText"],
                    "url": data.get("AbstractURL", ""),
                })
            for topic in data.get("RelatedTopics", [])[:max_results]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({
                        "title": topic.get("Text","")[:80],
                        "content": topic.get("Text",""),
                        "url": topic.get("FirstURL",""),
                    })
            return results
        except Exception:
            pass

    return [{"title": "Search unavailable", "content": f"Could not search: {query}", "url": ""}]


# ══════════════════════════════════════════════════════════
# MARKET RESEARCH TOOLS
# ══════════════════════════════════════════════════════════

def wikipedia_summary(company: str) -> Dict:
    if not _WIKIPEDIA:
        return {"title": company, "summary": "Wikipedia module not installed.", "url": "", "categories": []}
    try:
        wikipedia.set_lang("en")
        page = wikipedia.page(company, auto_suggest=True)
        summary = wikipedia.summary(company, sentences=8, auto_suggest=True)
        return {"title": page.title, "summary": summary, "url": page.url, "categories": page.categories[:5]}
    except wikipedia.exceptions.DisambiguationError as e:
        try:
            summary = wikipedia.summary(e.options[0], sentences=8)
            return {"title": e.options[0], "summary": summary, "url": "", "categories": []}
        except Exception:
            return {"title": company, "summary": "No Wikipedia entry found.", "url": "", "categories": []}
    except Exception as e:
        return {"title": company, "summary": f"Wikipedia lookup failed: {e}", "url": "", "categories": []}


def crunchbase_lookup(company: str) -> Dict:
    results = web_search(f"{company} crunchbase funding rounds investors", max_results=3)
    funding = web_search(f"{company} total funding raised series valuation", max_results=3)
    return {"source": "crunchbase_via_search", "results": results[:2], "funding_context": funding[:2]}


# ══════════════════════════════════════════════════════════
# FINANCIAL TOOLS
# ══════════════════════════════════════════════════════════

def get_financial_data(ticker: str) -> Dict:
    if not _YFINANCE:
        return {"ticker": ticker, "error": "yfinance not installed", "source": "missing_dep"}
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            "ticker": ticker,
            "company_name": info.get("longName", ticker),
            "market_cap": info.get("marketCap"),
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "currency": info.get("currency", "USD"),
            "revenue_ttm": info.get("totalRevenue"),
            "gross_profit": info.get("grossProfits"),
            "ebitda": info.get("ebitda"),
            "net_income": info.get("netIncomeToCommon"),
            "pe_ratio": info.get("trailingPE"),
            "ps_ratio": info.get("priceToSalesTrailing12Months"),
            "debt_to_equity": info.get("debtToEquity"),
            "cash": info.get("totalCash"),
            "free_cash_flow": info.get("freeCashflow"),
            "revenue_growth": info.get("revenueGrowth"),
            "employees": info.get("fullTimeEmployees"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "country": info.get("country"),
            "description": info.get("longBusinessSummary", "")[:500],
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e), "source": "yfinance_failed"}


def get_historical_prices(ticker: str, period: str = "1y") -> Dict:
    if not _YFINANCE:
        return {"ticker": ticker, "error": "yfinance not installed"}
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        if hist.empty:
            return {"ticker": ticker, "error": "No price history found"}
        prices = hist["Close"].tolist()
        dates = [str(d.date()) for d in hist.index]
        return {
            "ticker": ticker,
            "dates": dates[-30:],
            "prices": prices[-30:],
            "period_return": round(((prices[-1] - prices[0]) / prices[0]) * 100, 2),
            "highest": round(max(prices), 2),
            "lowest": round(min(prices), 2),
            "current": round(prices[-1], 2),
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


def resolve_ticker(company_name: str) -> str:
    known = {
        "grab": "GRAB", "sea limited": "SE", "sea": "SE",
        "gojek": None, "tokopedia": None, "lazada": None,
        "airbnb": "ABNB", "uber": "UBER", "lyft": "LYFT",
        "tesla": "TSLA", "apple": "AAPL", "google": "GOOGL",
        "microsoft": "MSFT", "amazon": "AMZN", "meta": "META",
        "netflix": "NFLX", "nvidia": "NVDA", "shopify": "SHOP",
        "notion": None, "stripe": None, "openai": None,
    }
    lower = company_name.lower().strip()
    if lower in known:
        return known[lower]
    if _YFINANCE:
        try:
            ticker = yf.Ticker(company_name.upper())
            info = ticker.info
            if info.get("longName"):
                return company_name.upper()
        except Exception:
            pass
    results = web_search(f"{company_name} stock ticker symbol NASDAQ NYSE", max_results=2)
    for r in results:
        content = r.get("content", "")
        matches = re.findall(r'\b([A-Z]{2,5})\b', content)
        if matches:
            return matches[0]
    return None


# ══════════════════════════════════════════════════════════
# NEWS & SENTIMENT TOOLS
# ══════════════════════════════════════════════════════════

def get_news(company: str, max_articles: int = 10) -> List[Dict]:
    articles = []
    if NEWS_API_KEY:
        try:
            from newsapi import NewsApiClient
            api = NewsApiClient(api_key=NEWS_API_KEY)
            response = api.get_everything(
                q=company, language="en", sort_by="publishedAt", page_size=max_articles,
            )
            for a in response.get("articles", []):
                articles.append({
                    "title": a.get("title", ""),
                    "description": a.get("description", ""),
                    "source": a.get("source", {}).get("name", ""),
                    "published_at": a.get("publishedAt", ""),
                    "url": a.get("url", ""),
                    "sentiment": None,
                })
            if articles:
                return articles
        except Exception:
            pass

    # Fallback: Google News RSS
    if _FEEDPARSER and _REQUESTS:
        try:
            import requests as req
            rss_url = f"https://news.google.com/rss/search?q={req.utils.quote(company)}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:max_articles]:
                articles.append({
                    "title": entry.get("title", ""),
                    "description": entry.get("summary", ""),
                    "source": entry.get("source", {}).get("title", "Google News"),
                    "published_at": entry.get("published", ""),
                    "url": entry.get("link", ""),
                    "sentiment": None,
                })
            return articles
        except Exception:
            pass

    results = web_search(f"{company} news latest", max_results=max_articles)
    return [{"title": r.get("title",""), "description": r.get("content","")[:200],
             "source": "web_search", "published_at": "", "url": r.get("url",""), "sentiment": None}
            for r in results]


def analyze_sentiment(text: str) -> Dict:
    positive_words = {
        "growth", "profit", "revenue", "expand", "launch", "award", "partner",
        "record", "success", "strong", "gain", "surge", "beat", "innovative",
        "investment", "funding", "raise", "acquire", "milestone", "leading",
        "profitable", "breakthrough", "efficient", "robust", "outperform",
    }
    negative_words = {
        "loss", "decline", "lawsuit", "fraud", "scandal", "layoff", "cut",
        "fail", "drop", "concern", "risk", "warn", "fine", "penalty", "probe",
        "investigate", "debt", "default", "miss", "disappoint", "crisis",
        "slump", "weak", "trouble", "difficulty", "resign", "departure",
    }
    text_lower = text.lower()
    pos = sum(1 for w in positive_words if w in text_lower)
    neg = sum(1 for w in negative_words if w in text_lower)
    if pos > neg + 1:
        label, score = "positive", round(0.5 + (pos - neg) * 0.05, 2)
    elif neg > pos + 1:
        label, score = "negative", round(0.5 + (neg - pos) * 0.05, 2)
    else:
        label, score = "neutral", 0.5
    return {"label": label, "score": min(score, 0.99), "pos_signals": pos, "neg_signals": neg}


def get_reddit_mentions(company: str) -> List[Dict]:
    reddit_id = os.getenv("REDDIT_CLIENT_ID")
    reddit_secret = os.getenv("REDDIT_CLIENT_SECRET")
    if reddit_id and reddit_secret and "your_" not in reddit_id:
        try:
            import praw
            reddit = praw.Reddit(
                client_id=reddit_id,
                client_secret=reddit_secret,
                user_agent=os.getenv("REDDIT_USER_AGENT", "DealRoomAI/1.0"),
            )
            posts = []
            for submission in reddit.subreddit("investing+startups+tech").search(company, limit=5, sort="new"):
                posts.append({
                    "title": submission.title,
                    "score": submission.score,
                    "subreddit": str(submission.subreddit),
                    "url": submission.url,
                    "sentiment": analyze_sentiment(submission.title),
                })
            return posts
        except Exception:
            pass
    results = web_search(f"site:reddit.com {company} investing", max_results=3)
    return [{"title": r.get("title",""), "score": 0, "subreddit": "reddit",
             "url": r.get("url",""), "sentiment": analyze_sentiment(r.get("content",""))}
            for r in results]


# ══════════════════════════════════════════════════════════
# RISK TOOLS — IMPROVED BALANCED QUERIES
# ══════════════════════════════════════════════════════════

def search_legal_issues(company: str) -> List[Dict]:
    """
    Search for legal issues using BALANCED queries.
    Uses neutral phrasing to avoid biased results.
    Also fetches positive/neutral company profile for context.
    """
    queries = [
        # Neutral recent news — not leading with negative keywords
        f"{company} company news 2024 2025",
        # Specific legal check — but balanced
        f"{company} legal regulatory update",
        # Only ONE targeted negative check
        f"{company} fine penalty settlement",
    ]
    all_results = []
    for q in queries:
        results = web_search(q, max_results=3)
        all_results.extend(results)
    return all_results


def search_positive_signals(company: str) -> List[Dict]:
    """
    NEW: Search for positive signals to balance risk assessment.
    """
    queries = [
        f"{company} growth expansion milestone 2024",
        f"{company} investment partnership award",
    ]
    all_results = []
    for q in queries:
        results = web_search(q, max_results=3)
        all_results.extend(results)
    return all_results


def search_founder_background(company: str) -> List[Dict]:
    """Search for founder background — neutral phrasing."""
    results = web_search(f"{company} CEO founder leadership team background", max_results=4)
    return results
