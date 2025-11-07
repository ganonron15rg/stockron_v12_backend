# ==============================================================
# 🔄 AlphaVantage Agent v13.5
# Backup for Yahoo Finance if rate-limited
# ==============================================================
import os, httpx

class AlphaAgent:
    def __init__(self):
        self.api_key = os.getenv("ALPHA_API_KEY", "")
        self.base = "https://www.alphavantage.co/query"

    def fetch(self, ticker: str):
        if not self.api_key:
            raise RuntimeError("AlphaVantage key not set")

        url = f"{self.base}?function=OVERVIEW&symbol={ticker}&apikey={self.api_key}"
        r = httpx.get(url, timeout=10.0)
        data = r.json()

        if "Symbol" not in data:
            raise RuntimeError("AlphaVantage returned no data")

        return {
            "raw_quote": {
                "symbol": data["Symbol"],
                "price": float(data.get("50DayMovingAverage", 0)),
                "pe": float(data.get("PERatio", 0)),
                "market_cap": float(data.get("MarketCapitalization", 0)),
                "eps_growth": float(data.get("QuarterlyEarningsGrowthYOY", 0)),
                "rev_growth": float(data.get("QuarterlyRevenueGrowthYOY", 0))
            },
            "source": "AlphaVantage"
        }
