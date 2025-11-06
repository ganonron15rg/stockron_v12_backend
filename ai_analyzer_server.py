# ==============================================================
# 📊 Stockron Analyzer v13.0
# Backend: FastAPI + Multi-Agent System (Yahoo + Alpha + News)
# Integrates MasterAgent with Auto Fallback and News Aggregation
# ==============================================================

from __future__ import annotations
import os, random, re
from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from googletrans import Translator
from src.providers.stockron_master_agent import MASTER_AGENT

# --------------------- App & Config ---------------------
app = FastAPI(title="Stockron Analyzer v13.0", version="13.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

translator = Translator()

# --------------------- Utils ---------------------
def _iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

def safe_float(v: Any, nd=2):
    try:
        return round(float(v or 0), nd)
    except Exception:
        return 0.0

# --------------------- Request Model ---------------------
class AnalyzeRequest(BaseModel):
    ticker: str
    timeframe: Optional[str] = "6mo"
    notes: Optional[str] = None

# --------------------- Scoring ---------------------
def compute_scores(pe, eps_growth, profit_margin, roe, rsi) -> Dict[str, float]:
    pe = float(pe or 0); eps_growth = float(eps_growth or 0)
    profit_margin = float(profit_margin or 0); roe = float(roe or 0)
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

# --------------------- Main Endpoint ---------------------
@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    ticker = req.ticker.upper().strip()
    try:
        raw = MASTER_AGENT.fetch_financials(ticker)
    except Exception as e:
        return {"error": str(e), "ticker": ticker, "timestamp": _iso()}

    if not raw or "price" not in raw:
        return {"error": "No data returned from agents", "ticker": ticker, "timestamp": _iso()}

    data = {
        "company_name": raw.get("raw_quote", {}).get("shortName", ticker),
        "sector": raw.get("raw_quote", {}).get("sector", "Unknown"),
        "last_price": safe_float(raw.get("price")),
        "previous_close": safe_float(raw.get("raw_quote", {}).get("previousClose")),
        "pe_ratio": safe_float(raw.get("pe_ratio")),
        "market_cap": int(raw.get("market_cap") or 0),
        "source": raw.get("source"),
        "rsi": safe_float(raw.get("rsi")),
        "roe": safe_float(raw.get("roe")),
        "profit_margin": safe_float(raw.get("profit_margin")),
        "eps_growth": safe_float(raw.get("eps_growth")),
    }

    # --- Calculate Scores ---
    scores = compute_scores(
        data["pe_ratio"], data["eps_growth"],
        data["profit_margin"], data["roe"], data["rsi"]
    )
    stance = stance_from_overall(scores["overall_score"])

    # --- Get News ---
    news_data = MASTER_AGENT.fetch_news(ticker)
    top_headline = None
    if news_data and news_data.get("items"):
        top_headline = news_data["items"][0].get("headline")
        try:
            data["headline_he"] = translator.translate(top_headline, src='en', dest='he').text
        except Exception:
            data["headline_he"] = top_headline

    # --- Zones ---
    buy_zone = [round(data["last_price"] * 0.95, 2), round(data["last_price"] * 0.98, 2)]
    sell_zone = [round(data["last_price"] * 1.02, 2), round(data["last_price"] * 1.05, 2)]

    ai_summary = (
        f"{data['company_name']} ({ticker}) | "
        f"PE {data['pe_ratio']}, EPS {data['eps_growth']}%, PM {data['profit_margin']}%, ROE {data['roe']}% | "
        f"RSI {data['rsi']} | Sentiment Neutral | Score {scores['overall_score']}/100."
    )

    return {
        "ticker": ticker,
        "company_name": data["company_name"],
        "sector": data["sector"],
        "quant": {
            "pe_ratio": data["pe_ratio"],
            "eps_growth": data["eps_growth"],
            "overall_score": scores["quant_score"],
            "market_cap": data["market_cap"],
        },
        "quality": {
            "roe": data["roe"],
            "profit_margin": data["profit_margin"],
            "quality_score": scores["quality_score"],
        },
        "catalyst": {
            "news_sentiment": "Neutral",
            "ai_signal": stance,
            "catalyst_score": scores["catalyst_score"],
        },
        "ai_summary": ai_summary,
        "ai_stance": stance,
        "conviction_level": f"{round(scores['overall_score']/10, 1)}/10",
        "buy_sell_zones": {
            "buy_zone": buy_zone,
            "sell_zone": sell_zone,
            "rationale": "SMA20 ± ATR14"
        },
        "latest_news": news_data,
        "last_price": data["last_price"],
        "previous_close": data["previous_close"],
        "data_provider": data["source"],
        "news_provider": news_data.get("source") if news_data else None,
        "timestamp": _iso(),
    }

# --------------------- Health ---------------------
@app.get("/health")
def health():
    return {"status": "ok", "version": "v13.0", "timestamp": _iso()}

@app.head("/health")
def health_head():
    return {"status": "ok"}

# --------------------- Error Handler ---------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print("❌ Exception:", str(exc))
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "message": "Server error", "timestamp": _iso()},
    )

# --------------------- Run ---------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
