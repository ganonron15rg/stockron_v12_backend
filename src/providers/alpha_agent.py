# providers/alpha_agent.py
# AlphaVantage fallback agent – free alternative to Yahoo
import os, time, random, httpx

ALPHA_KEY = os.getenv("ALPHAVANTAGE_KEY")

class AlphaAgent:
    def __init__(self):
        self.name = "AlphaAgent"
        self.client = httpx.Client(timeout=8.0)
        self.base = "https://www.alphavantage.co/query"

    def fetch(self, ticker: str):
        ticker = ticker.upper().strip()
        if not ALPHA_KEY:
            return None

        time.sleep(random.uniform(0.2, 0.6))

        try:
            # Fundamentals (overview)
            url = f"{self.base}?function=OVERVIEW&symbol={ticker}&apikey={ALPHA_KEY}"
            r = self.client.get(url)
            data = r.json()

            if not isinstance(data, dict) or not data.get("Symbol"):
                return None

            # Basic fields
            return {
                "provider": "alpha_vantage",
                "symbol": data.get("Symbol"),
                "company_name": data.get("Name"),
                "sector": data.get("Sector"),
                "pe_ratio": float(data.get("PERatio") or 0),
                "peg_ratio": float(data.get("PEGRatio") or 0),
                "ps_ratio": float(data.get("PriceToSalesRatioTTM") or 0),
                "profit_margin": float(data.get("ProfitMargin") or 0),
                "roe": float(data.get("ReturnOnEquityTTM") or 0),
                "rev_growth": float(data.get("QuarterlyRevenueGrowthYOY") or 0) * 100,
                "eps_growth": float(data.get("QuarterlyEarningsGrowthYOY") or 0) * 100,
                "dividend_yield": float(data.get("DividendYield") or 0) * 100,
                "market_cap": float(data.get("MarketCapitalization") or 0),
            }

        except Exception as e:
            print("AlphaAgent error:", e)
            return None
