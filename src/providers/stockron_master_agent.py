# ==============================================================
# 🤖 Stockron Master Agent v13.4 (Multi-Agent Final)
# Manages 10 Yahoo Agents with cooldown + Alpha fallback
# ==============================================================
import time
from src.providers.yahoo_agent import YahooAgent
from src.providers.alpha_agent import AlphaAgent
from src.providers.news_master_agent import NewsMasterAgent

class MasterAgent:
    def __init__(self):
        self.yahoo_agents = [YahooAgent(i) for i in range(1, 11)]  # 10 Yahoo agents
        self.alpha = AlphaAgent()
        self.news = NewsMasterAgent()
        self.index = 0

    def _get_next_yahoo(self):
        attempts = 0
        while attempts < len(self.yahoo_agents):
            agent = self.yahoo_agents[self.index]
            self.index = (self.index + 1) % len(self.yahoo_agents)
            if agent.is_available():
                return agent
            attempts += 1
        return None

    def fetch_financials(self, ticker: str):
        for attempt in range(len(self.yahoo_agents)):
            agent = self._get_next_yahoo()
            if not agent:
                break
            try:
                data = agent.fetch(ticker)
                if data and data.get("raw_quote"):
                    data["source"] = agent.name
                    return data
            except Exception as e:
                print(f"{agent.name} failed:", e)
                agent.set_cooldown(300)
                continue

        print("Yahoo rate limit reached – switching to AlphaVantage")
        return self.alpha.fetch(ticker)

    def fetch_news(self, ticker: str):
        return self.news.get_news(ticker)

MASTER_AGENT = MasterAgent()
