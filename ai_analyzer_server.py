# ==============================================================
# 📊 Stockron Analyzer v12.7
# Backend: FastAPI + Yahoo Finance + Finnhub + Google Translate
# Adds: RateLimit Protection, Error Handler, HEAD /health, Safe Fetch
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
        "rev_growth": safe_float(info.get("revenueGrowth") * 100),
        "eps_growth": safe_float(info.get("earningsQuarterlyGrowth") * 100),
        "market_cap": int(info.get("marketCap") or 0),
        "debt_equity": safe_float(info.get("debtToEquity")),
        "current_ratio": safe_float(info.get("currentRatio")),
        "profit_margin": safe_float(info.get("profitMargins") * 100),
        "roe": safe_float(info.get("returnOnEquity") * 100),
        "dividend_yield": safe_float(info.get("dividendYield") * 100),

        # Technical snapshot
        "sma20": safe_float(sma20.iloc[-1]),
        "sma50": safe_float(sma50.iloc[-1]),
        "rsi": safe_float(rsi.iloc[-1]),
        "macd": safe_float(macd.iloc[-1]),
        "signal": safe_float(signal.iloc[-1]),
    }

    # --- Chart Data ---
    df = pd.DataFrame({
        "date": hist.index.tz_localize(_
