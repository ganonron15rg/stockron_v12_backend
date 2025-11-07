# =============================================================
# 🧠 Stockron AI Analyzer Server v13.6
# Integrates async master agent + scoring system
# =============================================================
from fastapi import FastAPI
from pydantic import BaseModel
import random, asyncio
from datetime import datetime
from src.providers.stockron_master_agent import MASTER_AGENT

app = FastAPI()

class AnalyzeRequest(BaseModel):
    ticker: str

def _iso():
    return datetime.utcnow().isoformat() + "Z"

def safe_float(value, default=0.0):
    try:
        return float(value or 0)
    except Exception:
        return default

def compute_scores(pe, eps, pm, roe, rsi):
    quant = max(0, 100 - min(pe, 200) / 2)
    quality = min(100, (eps + pm + roe) / 3)
    catalyst = 100 - abs(rsi - 50)
    overall = round(quant * 0.4 + quality * 0.4 + catalyst * 0.2, 2)
    return {"quant": quant, "quality": quality, "catalyst": catalyst, "overall_score": overall}

def stance_from_overall(score):
    if score >= 75: return "Buy"
    elif score >= 50: return "Hold"
    else: return "Wait"

async def fetch_from_master(ticker: str):
    """פונקציה מאוחדת שמביאה נתונים מהמאסטר סוכן"""
    try:
        data = await MASTER_AGENT.fetch(ticker)
        return data
    except Exception as e:
        print("❌ fetch_from_master failed:", e)
        return {}

@app.get("/")
async def home():
    return {"status": "ok", "version": "v13.6"}

@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    ticker = req.ticker.upper().strip()
    try:
        base_data = await fetch_from_master(ticker)
    except Exception as e:
        return {"error": str(e), "ticker": ticker, "timestamp": _iso()}

    raw = base_data.get("raw_quote", {})
    if not raw:
        return {"error": "No data returned from agents", "ticker": ticker, "timestamp": _iso()}

    pe = safe_float(raw.get("pe"))
    eps = safe_float(raw.get("eps_growth") * 100)
    pm = safe_float(raw.get("rev_growth") * 100)
    roe = safe_float(raw.get("market_cap") / 1e12)
    rsi = random.uniform(40, 60)

    scores = compute_scores(pe, eps, pm, roe, rsi)
    stance = stance_from_overall(scores["overall_score"])

    return {
        "ticker": ticker,
        "scores": scores,
        "ai_stance": stance,
        "timestamp": _iso(),
        "source": base_data.get("source", "Unknown"),
    }
