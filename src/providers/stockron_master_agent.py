# providers/stockron_master_agent.py
# Stockron Master Agent – manages 10 Yahoo agents + Alpha fallback
import time, random
from src.providers.yahoo_agent import YahooAgent
from src.providers.alpha_agent import AlphaAgent

class MasterAgent:
    def __init__(self):
        self.yahoo_agents = [YahooAgent(i) for i in range(1, 11)]  # 10 סוכני Yahoo
        self.alpha = AlphaAgent()
        self.index = 0

    def _get_next_yahoo(self):
        """Round-robin – מחזיר את הסוכן הזמין הבא"""
        attempts = 0
        while attempts < len(self.yahoo_agents):
            agent = self.yahoo_agents[self.index]
            self.index = (self.index + 1) % len(self.yahoo_agents)
            if agent.is_available():
                return agent
            attempts += 1
        return None

    def fetch(self, ticker: str):
        # נסה כל אחד מהסוכנים לפי הסבב
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
                agent.set_cooldown(300)  # סמן ל־5 דקות קירור
                continue

        # fallback אם כולם חסומים
        print("Yahoo rate limit reached – switching to AlphaVantage")
        return self.alpha.fetch(ticker)

# יצירת מופע גלובלי
MASTER_AGENT = MasterAgent()
