from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import random, os

app = FastAPI(title="Stockron Analyzer Backend v12")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "v12",
        "service": "Stockron Backend",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

def mock_quant():
    return {
        "pe_ratio": round(random.uniform(5, 30), 2),
        "eps_growth": round(random.uniform(0, 25), 2),
        "rev_growth": round(random.uniform(0, 20), 2),
        "overall_score": round(random.uniform(40, 95), 1),
    }

def mock_quality():
    return {
        "debt_equity": round(random.uniform(0.1, 2.5), 2),
        "profit_margin": round(random.uniform(5, 40), 2),
        "roe": round(random.uniform(5, 30), 2),
        "quality_score": round(random.uniform(40, 90), 1),
    }

def mock_catalyst():
    return {
        "news_sentiment": random.choice(["Positive", "Neutral", "Negative"]),
        "sector_momentum": round(random.uniform(-5, 10), 1),
        "ai_signal": random.choice(["Strong Buy", "Buy", "Hold", "Sell"]),
    }

@app.post("/analyze")
async def analyze(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    ticker = (data.get("ticker") or "UNKNOWN").upper()

    quant = mock_quant()
    quality = mock_quality()
    catalyst = mock_catalyst()

    summary = (
        f"{ticker} | P/E={quant['pe_ratio']}, EPS {quant['eps_growth']}%, "
        f"PM {quality['profit_margin']}%, momentum {catalyst['sector_momentum']}%."
    )

    avg = quant["overall_score"]*0.4 + quality["quality_score"]*0.4 + max(0, catalyst["sector_momentum"]+50)*0.2
    stance = "Buy" if avg >= 70 else "Hold" if avg >= 55 else "Wait"

    return {
        "ticker": ticker,
        "quant": quant,
        "quality": quality,
        "catalyst": catalyst,
        "ai_summary": summary,
        "ai_stance": stance,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
