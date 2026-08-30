# scripts/probe_cse_endpoints.py
"""Discover which cse.lk JSON endpoints exist and what shape they return.

Run with:  python -m scripts.probe_cse_endpoints

Read-only. Sends one request per candidate path with the same headers the
scraper already uses, and prints status, size, and the top-level shape of each
response. Nothing is written to the database.

The point is to establish empirically what data is actually available before
building anything on it. The app currently hardcodes ASPI to 12450.80 / +1.2%
and renders it as live market data; replacing that needs a real source, and
guessing endpoint names would just move the fiction one layer down.

cse.lk's API is POST-based for the endpoints already in use (tradeSummary,
marketStatus), so each candidate is tried as POST and then, if that fails, GET.
A short delay separates requests -- this is someone else's public API.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from app.services.scraper import CSE_HEADERS

BASE = "https://www.cse.lk/api/"

# Candidates. The first two are known-good and act as a control: if they fail,
# the network or the headers are the problem, not the endpoint name.
CANDIDATES = [
    # -- controls, already used by the scraper
    "tradeSummary",
    "marketStatus",
    # -- indices (the actual goal of I-05)
    "aspiData",
    "snpData",
    "aspiIndexData",
    "indexData",
    "marketSummary",
    "dailyMarketSummery",      # cse.lk has historically misspelled this
    "dailyMarketSummary",
    "marketDepthData",
    # -- movers, which several screens currently fake
    "topGainers",
    "topLooses",               # cse.lk's own spelling
    "topLosers",
    "mostActiveTrades",
    "mostActiveVolumes",
    # -- per-company data, for I-07 fundamentals
    "companyInfoSummery",
    "companyInfoSummary",
    "companyProfile",
    # -- history, for I-06 charts
    "chartData",
    "historicalData",
    "todaySharePrice",
    "detailedTrades",
    "allSectors",
    "sectorSummary",
]


def shape(value: Any, depth: int = 0) -> str:
    """A compact description of a JSON value's structure."""
    pad = "  " * depth
    if isinstance(value, dict):
        if depth >= 2:
            return f"{{{len(value)} keys}}"
        lines = []
        for k, v in list(value.items())[:12]:
            lines.append(f"{pad}  {k}: {shape(v, depth + 1)}")
        extra = f"\n{pad}  ... {len(value) - 12} more keys" if len(value) > 12 else ""
        return "{\n" + "\n".join(lines) + extra + f"\n{pad}}}"
    if isinstance(value, list):
        if not value:
            return "[] (empty)"
        return f"[{len(value)} items] first = {shape(value[0], depth + 1)}"
    if isinstance(value, str):
        return f'str "{value[:40]}"' if len(value) <= 40 else f'str "{value[:40]}..."'
    return f"{type(value).__name__} {value}"


async def probe(client: httpx.AsyncClient, path: str) -> dict:
    url = BASE + path
    for method in ("POST", "GET"):
        try:
            r = await (client.post(url) if method == "POST" else client.get(url))
        except Exception as exc:
            return {"path": path, "method": method, "status": None,
                    "error": f"{type(exc).__name__}: {exc}"}
        if r.status_code == 200:
            try:
                return {"path": path, "method": method, "status": 200,
                        "bytes": len(r.content), "json": r.json()}
            except Exception:
                return {"path": path, "method": method, "status": 200,
                        "bytes": len(r.content), "text": r.text[:200]}
        last = {"path": path, "method": method, "status": r.status_code,
                "bytes": len(r.content)}
    return last


async def main() -> None:
    found, empty, missing = [], [], []

    async with httpx.AsyncClient(headers=CSE_HEADERS, timeout=30,
                                 follow_redirects=True) as client:
        for path in CANDIDATES:
            res = await probe(client, path)
            status = res.get("status")

            if status != 200:
                missing.append(res)
                print(f"[{status or 'ERR':>4}] {path:<22} "
                      f"{res.get('error', '')}")
            else:
                payload = res.get("json")
                is_empty = payload in (None, [], {}) or (
                    isinstance(payload, dict) and
                    all(v in (None, [], {}) for v in payload.values()))
                (empty if is_empty else found).append(res)
                flag = "EMPTY" if is_empty else " 200 "
                print(f"[{flag}] {path:<22} {res['method']:<5} "
                      f"{res.get('bytes', 0):>8} bytes")
            await asyncio.sleep(0.4)

    print("\n" + "=" * 74)
    print(f"  {len(found)} usable, {len(empty)} reachable-but-empty, "
          f"{len(missing)} unavailable")
    print("=" * 74)

    for res in found:
        print(f"\n{'-' * 74}\n{res['path']}  ({res['method']}, "
              f"{res['bytes']} bytes)\n{'-' * 74}")
        print(shape(res["json"]))

    if empty:
        print(f"\n{'-' * 74}\nReachable but empty (may only populate during a "
              f"trading session):\n{'-' * 74}")
        for res in empty:
            print(f"  {res['path']:<22} -> {json.dumps(res['json'])[:100]}")


if __name__ == "__main__":
    asyncio.run(main())
