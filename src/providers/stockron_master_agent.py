# =============================================================
# 📊 Stockron Master Agent v13.6
# Handles 10 Yahoo agents + Alpha fallback (Async safe version)
# =============================================================
import asyncio, random
from src.providers.yahoo_agent import YahooAgent
from src.providers.alpha_agent import AlphaAgent

class MasterAgent:
    def __init__(self):
        self.yahoo_agents = [YahooAgent(i) for i in range(1, 11)]
        self.alpha = AlphaAgent()
        self.index = 0

    def _get_next_yahoo(self):
        """Round-robin: בוחר את הסוכן הבא בתור"""
        attempts = 0
        while attempts < len(self.yahoo_agents):
            agent = self.yahoo_agents[self.index]
            self.index = (self.index + 1) % len(self.yahoo_agents)
            if agent.is_available():
                return agent
            attempts += 1
        return None

    async def fetch(self, ticker: str):
        """שולח בקשה ל־Yahoo ואם חסום עובר ל־Alpha"""
        for attempt in range(len(self.yahoo_agents)):
            agent = self._get_next_yahoo()
            if not agent:
                break
            try:
                data = await agent.fetch(ticker)
                if data and data.get("raw_quote"):
                    data["source"] = agent.name
                    print(f"✅ Data fetched from {agent.name}")
                    return data
            except Exception as e:
                print(f"⚠️ {agent.name} failed:", e)
                agent.set_cooldown(300)
                continue

        print("🟡 Yahoo rate limit reached – switching to AlphaVantage")
        return await self.alpha.fetch(ticker)

MASTER_AGENT = MasterAgent()
