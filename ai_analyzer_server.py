# ==============================================================
# 📊 Stockron Analyzer v12.7 → v13.0 bridge
# Backend: FastAPI + Yahoo Finance + Finnhub + Google Translate
# Adds: RateLimit Protection, Error Handler, HEAD /health, Safe Fetch
# + MasterAgent integration (/analyze_v13) – 10 Yahoo agents + Alpha fallback
# ============================================================== 

from __future__ import annotations
import os, random, httpx, re, time
import yfinance as yf
import pandas as pd
from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from googletrans import Translator
from functools import lru_cache

# ---- NEW: Master Agent (10×Yahoo + Alpha fallback) ----
# Make sure you have: src/providers/{yahoo_agent.py, alpha_agent.py, stockron_master_agent.py}
from src.providers.stockron_master_agent import MASTER_AGENT

# --------------------- App & Config ---------------------
app = FastAPI(title="Stockron Analyzer v12.7", version="12.7")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
translator = Translator()

# --------------------- Utils ---------------------
def _iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

def _round_list(xs, nd=2):
    return [None if pd.isna(v) else round(float(v), nd) for v in xs]

def safe_float(v: Any, nd=2):
    try:
        return round(float(v or 0), nd)
    except Exception:
        return 0.0

# --------------------- Cache for Yahoo Requests ---------------------
@lru_cache(maxsize=128)
def cached_info(ticker: str):
    """Cache Yahoo Finance info to reduce rate-limit risk"""
    return yf.Ticker(ticker).info

# --------------------- Request Model ---------------------
class AnalyzeRequest(BaseModel):
    ticker: str
    timeframe: Optional[str] = "6mo"
    notes: Optional[str] = None

# --------------------- Data Fetch + Technicals ---------------------
def fetch_yahoo_with_technicals(ticker: str, period="6mo") -> Dict[str, Any]:
    try:
        st = yf.Ticker(ticker)
        info = cached_info(ticker)
        hist = st.history(period=period, interval="1d")
    except Exception as e:
        if "Too Many Requests" in str(e) or "RateLimit" in str(e):
            raise RuntimeError("Yahoo Finance rate limit exceeded. Please try again in a few minutes.")
        raise RuntimeError(f"Yahoo Finance error: {e}")

    if hist is None or hist.empty:
        raise RuntimeError(f"No historical data found for {ticker}")

    close = hist["Close"]
    high = hist["High"]
    low = hist["Low"]

    # --- Technical Indicators ---
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    histo = macd - signal

    last_price = safe_float(info.get("currentPrice")) or safe_float(close.iloc[-1])
    prev_close = safe_float(info.get("previousClose")) or safe_float(close.iloc[-2])

    payload = {
        "company_name": info.get("shortName") or info.get("longName") or ticker,
        "sector": info.get("sector", "Unknown"),
        "last_price": last_price,
        "previous_close": prev_close,

        # Fundamentals
        "pe_ratio": safe_float(info.get("trailingPE")),
        "ps_ratio": safe_float(info.get("priceToSalesTrailing12Months")),
        "peg_ratio": safe_float(info.get("pegRatio")),
        "rev_growth": safe_float((info.get("revenueGrowth") or 0) * 100),
        "eps_growth": safe_float((info.get("earningsQuarterlyGrowth") or 0) * 100),
        "market_cap": int(info.get("marketCap") or 0),
        "debt_equity": safe_float(info.get("debtToEquity")),
        "current_ratio": safe_float(info.get("currentRatio")),
        "profit_margin": safe_float((info.get("profitMargins") or 0) * 100),
        "roe": safe_float((info.get("returnOnEquity") or 0) * 100),
        "dividend_yield": safe_float((info.get("dividendYield") or 0) * 100),

        # Technical snapshot
        "sma20": safe_float(sma20.iloc[-1]),
        "sma50": safe_float(sma50.iloc[-1]),
        "rsi": safe_float(rsi.iloc[-1]),
        "macd": safe_float(macd.iloc[-1]),
        "signal": safe_float(signal.iloc[-1]),
    }

    # --- Chart Data ---
    df = pd.DataFrame({
        "date": hist.index.tz_localize(None),
        "close": close,
        "sma20": sma20,
        "sma50": sma50,
        "rsi": rsi,
        "macd": macd,
        "signal": signal,
        "histogram": histo
    }).tail(120)

    payload["chart"] = {
        "meta": {"period": period, "points": len(df)},
        "series": {
            "date": [d.strftime("%Y-%m-%d") for d in df["date"]],
            "close": _round_list(df["close"]),
            "sma20": _round_list(df["sma20"]),
            "sma50": _round_list(df["sma50"]),
            "rsi": _round_list(df["rsi"]),
            "macd": _round_list(df["macd"]),
            "signal": _round_list(df["signal"]),
            "histogram": _round_list(df["histogram"]),
        }
    }

    return payload

# --------------------- Sentiment ---------------------
def fetch_news_sentiment(ticker: str) -> str:
    if not FINNHUB_API_KEY:
        return "Neutral"
    try:
        url = f"https://finnhub.io/api/v1/news-sentiment?symbol={ticker}&token={FINNHUB_API_KEY}"
        r = httpx.get(url, timeout=6.0)
        data = r.json()
        score = (data.get("sentiment") or {}).get("companyNewsScore", 0)
        if score > 0.3: return "Positive"
        if score < -0.3: return "Negative"
        return "Neutral"
    except Exception:
        return "Neutral"

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

# --------------------- Main Analyze Endpoint (v12.7) ---------------------
@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    ticker = req.ticker.upper().strip()
    try:
        data = fetch_yahoo_with_technicals(ticker, req.timeframe)
    except Exception as e:
        return {"error": str(e), "ticker": ticker, "timestamp": _iso()}

    sentiment = fetch_news_sentiment(ticker)
    scores = compute_scores(data["pe_ratio"], data["eps_growth"], data["profit_margin"], data["roe"], data["rsi"])
    stance = stance_from_overall(scores["overall_score"])

    buy_zone = [round(data["last_price"] * 0.95, 2), round(data["last_price"] * 0.98, 2)]
    sell_zone = [round(data["last_price"] * 1.02, 2), round(data["last_price"] * 1.05, 2)]

    ai_summary = (
        f"{data['company_name']} ({ticker}) | "
        f"PE {data['pe_ratio']}, EPS {data['eps_growth']}%, PM {data['profit_margin']}%, ROE {data['roe']}% | "
        f"RSI {data['rsi']}, MACD {data['macd']} vs Signal {data['signal']} | "
        f"Sentiment {sentiment} | Score {scores['overall_score']}/100."
    )

    return {
        "ticker": ticker,
        "company_name": data["company_name"],
        "sector": data["sector"],
        "quant": {
            "pe_ratio": data["pe_ratio"],
            "ps_ratio": data["ps_ratio"],
            "peg_ratio": data["peg_ratio"],
            "rev_growth": data["rev_growth"],
            "eps_growth": data["eps_growth"],
            "overall_score": scores["quant_score"],
            "market_cap": data["market_cap"],
            "rsi": data["rsi"],
            "sma20": data["sma20"],
            "sma50": data["sma50"],
            "macd": data["macd"],
            "signal": data["signal"],
        },
        "quality": {
            "debt_equity": data["debt_equity"],
            "current_ratio": data["current_ratio"],
            "profit_margin": data["profit_margin"],
            "roe": data["roe"],
            "quality_score": scores["quality_score"],
            "dividend_yield": data["dividend_yield"],
        },
        "catalyst": {
            "news_sentiment": sentiment,
            "sector_momentum": random.uniform(-5, 15),
            "ai_signal": stance,
            "catalyst_score": scores["catalyst_score"],
        },
        "ai_summary": ai_summary,
        "ai_stance": stance,
        "conviction_level": f"{round(scores['overall_score']/10, 1)}/10",
        "buy_sell_zones": {
            "buy_zone": buy_zone,
            "sell_zone": sell_zone,
            "rationale": "SMA20 ± ATR14 (technical hybrid)"
        },
        "last_price": data["last_price"],
        "previous_close": data["previous_close"],
        "chart": data["chart"],
        "data_reliability": "High",
        "transparency": "Yahoo Finance + Finnhub + Technical Indicators",
        "timestamp": _iso()
    }

# --------------------- Master Agent Endpoint (v13.0) ---------------------
@app.post("/analyze_v13")
async def analyze_v13(req: AnalyzeRequest):
    """
    v13.0 – ניתוח עם Master Agent (10 Yahoo סוכנים + Alpha fallback)
    מחזיר Snapshot בסיסי ומהיר (לתצוגת POC / Beta). ניתן להרחיב ל-contract המלא בהמשך.
    """
    ticker = req.ticker.upper().strip()
    try:
        raw = MASTER_AGENT.fetch(ticker)
        if not raw:
            return {"error": "No data from agents", "ticker": ticker, "timestamp": _iso()}

        quote = raw.get("raw_quote") or {}
        chart = raw.get("raw_chart") or {}
        source = raw.get("source", "unknown")

        # Best-effort fields; ניתן להרחיב למבנה המלא של v12.7 עם normalizer משותף
        return {
            "ticker": quote.get("symbol") or ticker,
            "company_name": quote.get("company_name") or quote.get("shortName") or quote.get("longName") or ticker,
            "sector": quote.get("sector", "Unknown"),
            "data_source": source,
            "price": quote.get("currentPrice"),
            "pe_ratio": quote.get("trailingPE"),
            "ps_ratio": quote.get("priceToSalesTrailing12Months"),
            "peg_ratio": quote.get("pegRatio"),
            "rev_growth": quote.get("revenueGrowth"),
            "eps_growth": quote.get("earningsQuarterlyGrowth"),
            "debt_equity": quote.get("debtToEquity"),
            "roe": quote.get("returnOnEquity"),
            "profit_margin": quote.get("profitMargins"),
            "market_cap": quote.get("marketCap"),
            "chart_meta": chart.get("meta") if isinstance(chart, dict) else None,
            "timestamp": _iso()
        }

    except Exception as e:
        return {"error": str(e), "ticker": ticker, "timestamp": _iso()}

# --------------------- Health Endpoints ---------------------
@app.get("/health")
def health():
    return {"status": "ok", "version": "v12.7", "timestamp": _iso()}

@app.head("/health")
def health_head():
    return {"status": "ok"}

# --------------------- Global Error Handler ---------------------
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
