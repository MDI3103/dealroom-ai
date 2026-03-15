"""
Simple in-memory cache with TTL.
Prevents re-fetching the same company data within 1 hour.
"""
import time
import json
from typing import Any, Optional, Dict

class AnalysisCache:
    def __init__(self, ttl_seconds: int = 3600):
        self._store: Dict[str, Dict] = {}
        self._ttl = ttl_seconds

    def _key(self, company: str) -> str:
        return company.lower().strip()

    def get(self, company: str) -> Optional[Dict]:
        key = self._key(company)
        if key in self._store:
            entry = self._store[key]
            if time.time() - entry["timestamp"] < self._ttl:
                return entry["data"]
            else:
                del self._store[key]
        return None

    def set(self, company: str, data: Dict):
        self._store[self._key(company)] = {
            "data": data,
            "timestamp": time.time(),
        }

    def list_cached(self):
        now = time.time()
        return [
            {"company": k, "age_minutes": round((now - v["timestamp"]) / 60, 1)}
            for k, v in self._store.items()
            if now - v["timestamp"] < self._ttl
        ]

    def clear(self, company: str = None):
        if company:
            self._store.pop(self._key(company), None)
        else:
            self._store.clear()

# Global singleton
cache = AnalysisCache(ttl_seconds=3600)
