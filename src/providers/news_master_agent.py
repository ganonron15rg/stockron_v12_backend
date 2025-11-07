# ==============================================================
# 🗞️ Stockron News Master Agent v13.5
# Aggregates Yahoo, MarketWatch, Google RSS feeds (Free only)
# ==============================================================
import httpx, xml.etree.ElementTree as ET
from datetime import datetime
from googletrans import Translator

translator = Translator()

class RSSAgentBase:
    def parse_rss(self, rss_text, source):
        root = ET.fromstring(rss_text)
        items = []
        for item in root.findall(".//item")[:8]:
            items.append({
                "headline": item.find("title").text,
                "url": item.find("link").text,
                "datetime": item.find("pubDate").text,
                "source": source
            })
        return items

class YahooNewsAgent(RSSAgentBase):
    async def fetch(self, ticker: str):
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
        r = httpx.get(url, timeout=6.0)
        return self.parse_rss(r.text, "Yahoo Finance")

class MarketWatchAgent(RSSAgentBase):
    async def fetch(self, ticker: str):
        url = f"https://feeds.marketwatch.com/marketwatch/stock/{ticker}"
        r = httpx.get(url, timeout=6.0)
        return self.parse_rss(r.text, "MarketWatch")

class GoogleNewsAgent(RSSAgentBase):
    async def fetch(self, ticker: str):
        q = ticker.replace("^", "").replace(".", "")
        url = f"https://news.google.com/rss/search?q={q}+stock"
        r = httpx.get(url, timeout=6.0)
        return self.parse_rss(r.text, "Google News")

class NewsMasterAgent:
    def __init__(self):
        self.agents = [YahooNewsAgent(), MarketWatchAgent(), GoogleNewsAgent()]
        self.index = 0

    async def get_news(self, ticker: str):
        for i in range(len(self.agents)):
            agent = self.agents[(self.index + i) % len(self.agents)]
            try:
                raw_news = await agent.fetch(ticker)
                self.index = (self.index + 1) % len(self.agents)
                translated = []
                for n in raw_news:
                    try:
                        he = translator.translate(n["headline"], src="en", dest="he").text
                        translated.append({**n, "headline_he": he})
                    except Exception:
                        translated.append(n)
                return {
                    "ticker": ticker,
                    "count": len(translated),
                    "items": translated,
                    "source": agent.__class__.__name__,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
            except Exception as e:
                print(f"⚠️ {agent.__class__.__name__} failed: {e}")
        return {"ticker": ticker, "count": 0, "items": [], "source": "None"}
