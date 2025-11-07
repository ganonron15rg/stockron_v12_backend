# ==============================================================
# 📈 Finnhub Agent v13.5
# Fetch sentiment and fundamentals from Finnhub
# ==============================================================
import os, httpx

class FinnhubAgent:
    def __init__(self):
        self.api_key = os.getenv("FINNHUB_API_KEY", "")
        self.base = "https://finnhub.io/api/v1"

    def fetch(self, ticker: str):
        if not self.api_key:
            raise RuntimeError("Finnhub API key missing")

        url = f"{self.base}/quote?symbol={ticker}&token={self.api_key}"
        r = httpx.get(url, timeout=8.0)
        data = r.json()

        if "c" not in data:
            raise RuntimeError("Invalid Finnhub response")

        sentiment_url = f"{self.base}/news-sentiment?symbol={ticker}&token={self.api_key}"
        sentiment = httpx.get(sentiment_url, timeout=6.0).json()

        score = (sentiment.get("sentiment") or {}).get("companyNewsScore", 0)
        if score > 0.3:
            sentiment_label = "Positive"
        elif score < -0.3:
            sentiment_label = "Negative"
        else:
            sentiment_label = "Neutral"

        return {
            "raw_quote": {
                "symbol": ticker,
                "price": data.get("c"),
                "high": data.get("h"),
                "low": data.get("l"),
                "sentiment": sentiment_label,
            },
            "source": "Finnhub"
        }
