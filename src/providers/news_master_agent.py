# ==============================================================
# 🧠 Stockron Master Agent v13.5
# Manages 10 Yahoo Agents + AlphaVantage + Finnhub fallback
# ==============================================================
import time, random
from src.providers.yahoo_agent import YahooAgent
from src.providers.alpha_agent import AlphaAgent
from src.providers.finnhub_agent import FinnhubAgent

class MasterAgent:
    def __init__(self):
        self.yahoo_agents = [YahooAgent(i) for i in range(1, 11)]
        self.alpha = AlphaAgent()
        self.finnhub = FinnhubAgent()
        self.index = 0

    def _get_next_yahoo(self):
        for _ in range(len(self.yahoo_agents)):
            agent = self.yahoo_agents[self.index]
            self.index = (self.index + 1) % len(self.yahoo_agents)
            if agent.is_available():
                return agent
        return None

    def fetch(self, ticker: str):
        for _ in range(len(self.yahoo_agents)):
            agent = self._get_next_yahoo()
            if not agent:
                break
            try:
                data = agent.fetch(ticker)
                if data and data.get("raw_quote"):
                    data["source"] = agent.name
                    return data
            except Exception as e:
                print(f"⚠️ {agent.name} failed:", e)
                agent.set_cooldown(300)
                continue

        # fallback לשירותים נוספים
        print("🚨 Yahoo blocked – trying AlphaVantage or Finnhub")
        try:
            return self.alpha.fetch(ticker)
        except Exception:
            return self.finnhub.fetch(ticker)

MASTER_AGENT = MasterAgent()
