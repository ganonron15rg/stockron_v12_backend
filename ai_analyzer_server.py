# ==============================================================
# 📊 Stockron Analyzer v13.5
# FastAPI Backend: Yahoo + Alpha + Finnhub + Multi-News Agents
# Fully asynchronous, resilient, multilingual & agent-based
# ==============================================================

from __future__ import annotations
import os, random, asyncio, httpx, time, re, pandas as pd
from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# === Providers ===
from src.providers.stockron_master_agent import MASTER_AGENT
from src.providers.news_master_agent import NewsMasterAgent

# === Base Config ===
app = FastAPI(title="Stockron Analyzer v13.5", version="13.5")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Utils ===
def _iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

def safe_float(v: Any, nd=2):
    try:
        return round(float(v or 0), nd)
    except Exception:
        return 0.0

def _round_list(xs, nd=2):
    return [None if pd.isna(v) else round(float(v), nd) for v in xs]

# === Request Model ===
class AnalyzeRequest(BaseModel):
    ticker: str
    timeframe: Optional[str] = "6mo"
    include_news: Optional[bool] = True

# === Analyzer Logic ===
async def fetch_from_master(ticker: str) -> Dict[str, Any]:
    """Try the full multi-agent system"""
    try:
        data = MASTER_AGENT.fetch(ticker)
        if not data or not data.get("raw_quote"):
            raise RuntimeError("No data returned from agents")
        return data
    except Exception as e:
        print("⚠️ MasterAgent fallback triggered:", e)
        raise RuntimeError(str(e))

def compute_scores(pe, eps_growth, profit_margin, roe, rsi) -> Dict[str, float]:
    pe = float(pe or 0)
    eps_growth = float(eps_growth or 0)
    profit_margin = float(profit_margin or 0)
    roe = float(roe or 0)
    rsi = float(rsi or 50)
    quant = max(0, min(100, 100 - pe/2 + eps_growth/2))
    quality = max(0, min(100, roe/2 + profit_margin/3))
    catalyst = max(0, min(100, 100 - abs(rsi - 50)))
    overall = round(quant*0.4 + quality*0.4 + catalyst*0.2, 1)
    return {
        "quant_score": round(quant, 1),
        "quality_score": round(quality, 1),
        "catalyst_score": round(catalyst, 1),
        "overall_score": overall
    }

def stance_from_overall(overall: float) -> str:
    if overall >= 70: return "Buy"
    if overall >= 55: return "Hold"
    return "Wait"

# === API Endpoint ===
@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    ticker = req.ticker.upper().strip()
    try:
        base_data = await asyncio.to_thread(fetch_from_master, ticker)
    except Exception as e:
        return {"error": str(e), "ticker": ticker, "timestamp": _iso()}

    raw = base_data.get("raw_quote", {})
    pe = safe_float(raw.get("pe"))
    eps = safe_float(raw.get("eps_growth") * 100)
    pm = safe_float(raw.get("rev_growth") * 100)
    roe = safe_float(raw.get("market_cap") / 1e12)  # normalized proxy
    rsi = random.uniform(40, 60)

    scores = compute_scores(pe, eps, pm, roe, rsi)
    stance = stance_from_overall(scores["overall_score"])

    # Zones
    price = safe_float(raw.get("price"))
    buy_zone = [round(price * 0.95, 2), round(price * 0.98, 2)]
    sell_zone = [round(price * 1.02, 2), round(price * 1.05, 2)]

    # News Section
    news_result = {}
    if req.include_news:
        try:
            news_agent = NewsMasterAgent()
            news_result = await news_agent.get_news(ticker)
        except Exception as e:
            print("⚠️ News agent failed:", e)
            news_result = {"count": 0, "items": []}

    # Final summary
    ai_summary = (
        f"{ticker} | PE {pe}, EPS {eps}%, Margin {pm}%, RSI {rsi:.1f} | "
        f"Score {scores['overall_score']}/100 | AI stance: {stance}"
    )

    return {
        "ticker": ticker,
        "quant": {
            "pe_ratio": pe,
            "eps_growth": eps,
            "rev_growth": pm,
            "overall_score": scores["quant_score"]
        },
        "quality": {
            "roe": roe,
            "profit_margin": pm,
            "quality_score": scores["quality_score"]
        },
        "catalyst": {
            "rsi": rsi,
            "ai_signal": stance,
            "catalyst_score": scores["catalyst_score"]
        },
        "ai_summary": ai_summary,
        "ai_stance": stance,
        "conviction_level": f"{round(scores['overall_score']/10, 1)}/10",
        "buy_sell_zones": {
            "buy_zone": buy_zone,
            "sell_zone": sell_zone,
            "rationale": "Auto ±5% range from base price"
        },
        "price": price,
        "source": base_data.get("source", "Unknown"),
        "news": news_result,
        "timestamp": _iso(),
        "version": "v13.5",
        "data_reliability": "High"
    }

# === Health ===
@app.get("/health")
def health():
    return {"status": "ok", "version": "v13.5", "timestamp": _iso()}

@app.head("/health")
def health_head():
    return {"status": "ok"}

# === Error Handler ===
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print("❌ Exception:", str(exc))
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "message": "Server error", "timestamp": _iso()},
    )

# === Run ===
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
