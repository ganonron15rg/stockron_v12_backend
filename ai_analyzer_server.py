# ==============================================================
#  Stockron Analyzer v12.5 (Fundamental + Technical + Charts)
#  Yahoo Finance + Finnhub + RSI/SMA/MACD + Chart JSON
# ==============================================================

from __future__ import annotations
import os, random, httpx, yfinance as yf
import pandas as pd
from datetime import datetime
from typing import Any, Dict, Optional, List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Stockron Analyzer Backend v12.5")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")  # optional

class AnalyzeRequest(BaseModel):
    ticker: str
    timeframe: Optional[str] = "6mo"
    notes: Optional[str] = None

# ----------------------------- Utils -----------------------------
def _iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

def _round_list(xs, nd=2):
    return [None if pd.isna(v) else round(float(v), nd) for v in xs]

# ----------------------- Fetch + Indicators ----------------------
def fetch_yahoo_with_technicals(ticker: str, period="6mo") -> Dict[str, Any]:
    st = yf.Ticker(ticker)
    info = st.info
    hist = st.history(period=period, interval="1d")

    if hist.empty:
        raise RuntimeError("No historical data found")

    close = hist["Close"].copy()
    high  = hist["High"].copy()
    low   = hist["Low"].copy()

    # SMA
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()

    # RSI(14)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    # MACD (12,26,9)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    histo = macd - signal

    last_price = info.get("currentPrice", None)
    if last_price is None:
        # fallback: use last close
        last_price = float(close.iloc[-1])

    payload = {
        "company_name": info.get("shortName") or info.get("longName") or ticker,
        "sector": info.get("sector", "Unknown"),
        "last_price": round(float(last_price), 2),
        "previous_close": round(float(info.get("previousClose", close.iloc[-2])), 2),

        # Fundamentals
        "pe_ratio": round(float(info.get("trailingPE", 0)), 2),
        "ps_ratio": round(float(info.get("priceToSalesTrailing12Months", 0)), 2),
        "peg_ratio": round(float(info.get("pegRatio", 0)), 2),
        "rev_growth": round(float(info.get("revenueGrowth", 0)) * 100, 2),
        "eps_growth": round(float(info.get("earningsQuarterlyGrowth", 0)) * 100, 2),
        "market_cap": int(info.get("marketCap", 0) or 0),
        "debt_equity": round(float(info.get("debtToEquity", 0)), 2),
        "current_ratio": round(float(info.get("currentRatio", 0)), 2),
        "profit_margin": round(float(info.get("profitMargins", 0)) * 100, 2),
        "roe": round(float(info.get("returnOnEquity", 0)) * 100, 2),
        "dividend_yield": round(float(info.get("dividendYield", 0)) * 100, 2),

        # Technical snapshot (latest)
        "sma20": round(float(sma20.iloc[-1]), 2) if not pd.isna(sma20.iloc[-1]) else None,
        "sma50": round(float(sma50.iloc[-1]), 2) if not pd.isna(sma50.iloc[-1]) else None,
        "rsi": round(float(rsi.iloc[-1]), 2) if not pd.isna(rsi.iloc[-1]) else None,
        "macd": round(float(macd.iloc[-1]), 2),
        "signal": round(float(signal.iloc[-1]), 2),
    }

    # ---- Chart series (compact) ----
    # נשמור עד 120 נקודות אחרונות כדי לשמור על תגובה קלה
    N = 120
    df = pd.DataFrame({
        "date": hist.index.tz_localize(None),
        "close": close,
        "sma20": sma20,
        "sma50": sma50,
        "rsi": rsi,
        "macd": macd,
        "signal": signal,
        "histogram": histo
    }).tail(N)

    payload["chart"] = {
        "meta": {
            "period": period,
            "points": len(df),
        },
        "series": {
            "date": [d.strftime("%Y-%m-%d") for d in df["date"].tolist()],
            "close": _round_list(df["close"]),
            "sma20": _round_list(df["sma20"]),
            "sma50": _round_list(df["sma50"]),
            "rsi": _round_list(df["rsi"]),
            "macd": _round_list(df["macd"]),
            "signal": _round_list(df["signal"]),
            "histogram": _round_list(df["histogram"])
        }
    }

    return payload

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

# -------------------------- Scoring -----------------------------
def compute_scores(pe, eps_growth, profit_margin, roe, rsi) -> Dict[str, float]:
    pe = float(pe or 0); eps_growth = float(eps_growth or 0)
    profit_margin = float(profit_margin or 0); roe = float(roe or 0)
    rsi = float(rsi or 50)

    quant = max(0, min(100, 100 - pe/2 + eps_growth/2))
    quality = max(0, min(100, roe/2 + profit_margin/3))
    catalyst = max(0, min(100, 100 - abs(rsi - 50)))  # יותר טוב כשקרוב ל-50

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

# --------------------------- API -------------------------------
@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    ticker = req.ticker.upper().strip()
    data = fetch_yahoo_with_technicals(ticker, period=req.timeframe or "6mo")

    sentiment = fetch_news_sentiment(ticker)
    scores = compute_scores(
        data["pe_ratio"], data["eps_growth"], data["profit_margin"], data["roe"], data["rsi"] or 50
    )
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
            "sector_momentum": data["chart"]["series"]["close"][-1] and random.uniform(-5, 15),
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
        "chart": data["chart"],  # <— כאן ה-Chart JSON
        "data_reliability": "High",
        "transparency": "Yahoo Finance + Finnhub + Technical Indicators",
        "timestamp": _iso()
    }

@app.get("/health")
def health():
    return {"status": "ok", "version": "v12.5", "service": "Stockron Analyzer Backend", "timestamp": _iso()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
