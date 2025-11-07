import httpx, os
from datetime import datetime

class AlphaAgent:
    def __init__(self):
        self.api_key = os.getenv("ALPHAVANTAGE_KEY", "demo")

    def fetch(self, ticker: str):
        url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={self.api_key}"
        r = httpx.get(url, timeout=8.0)
        data = r.json()
        if "Name" not in data:
            return None
        return {
            "raw_quote": data,
            "symbol": ticker,
            "price": data.get("50DayMovingAverage"),
            "pe_ratio": data.get("PERatio"),
            "market_cap": data.get("MarketCapitalization"),
            "source": "AlphaVantage",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
