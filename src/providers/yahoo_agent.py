# ==============================================================
# 🦾 Yahoo Agent v13.5
# Single Yahoo Finance fetcher with cooldown protection
# ==============================================================
import time, yfinance as yf

class YahooAgent:
    def __init__(self, agent_id: int):
        self.name = f"YahooAgent-{agent_id}"
        self.last_used = 0
        self.cooldown_until = 0

    def is_available(self) -> bool:
        return time.time() >= self.cooldown_until

    def set_cooldown(self, seconds: int = 300):
        self.cooldown_until = time.time() + seconds
        print(f"⏸️ {self.name} cooling down for {seconds}s")

    def fetch(self, ticker: str):
        try:
            self.last_used = time.time()
            stock = yf.Ticker(ticker)
            info = stock.info
            hist = stock.history(period="6mo", interval="1d")

            if hist.empty:
                raise ValueError("No historical data")

            return {
                "raw_quote": {
                    "symbol": ticker.upper(),
                    "price": float(info.get("currentPrice", 0)),
                    "pe": float(info.get("trailingPE", 0)),
                    "market_cap": float(info.get("marketCap", 0)),
                    "eps_growth": float(info.get("earningsQuarterlyGrowth", 0) or 0),
                    "rev_growth": float(info.get("revenueGrowth", 0) or 0),
                },
                "history_points": len(hist),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "agent": self.name
            }

        except Exception as e:
            print(f"❌ {self.name} failed for {ticker}: {e}")
            self.set_cooldown(180)
            raise e
