import yfinance as yf, time

class YahooAgent:
    def __init__(self, id: int):
        self.id = id
        self.name = f"YahooAgent#{id}"
        self.cooldown_until = 0

    def is_available(self):
        return time.time() > self.cooldown_until

    def set_cooldown(self, seconds: int):
        self.cooldown_until = time.time() + seconds

    def fetch(self, ticker: str):
        st = yf.Ticker(ticker)
        info = st.info
        hist = st.history(period="6mo", interval="1d")
        return {
            "raw_quote": info,
            "symbol": ticker,
            "price": info.get("currentPrice"),
            "pe_ratio": info.get("trailingPE"),
            "market_cap": info.get("marketCap"),
            "history_len": len(hist),
            "source": self.name
        }
