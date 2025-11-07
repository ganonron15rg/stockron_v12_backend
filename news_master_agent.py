import httpx, xml.etree.ElementTree as ET
from datetime import datetime
from googletrans import Translator
translator = Translator()

class YahooNewsAgent:
    def fetch(self, ticker: str):
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
        r = httpx.get(url, timeout=6.0)
        return self._parse(r.text, source="Yahoo Finance")
    def _parse(self, rss_text, source):
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

class MarketWatchAgent:
    def fetch(self, ticker: str):
        url = f"https://feeds.marketwatch.com/marketwatch/stock/{ticker}"
        r = httpx.get(url, timeout=6.0)
        return self._parse(r.text, source="MarketWatch")
    def _parse(self, rss_text, source):
        try:
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
        except Exception:
            return []

class GoogleNewsAgent:
    def fetch(self, ticker: str):
        url = f"https://news.google.com/rss/search?q={ticker}+stock"
        r = httpx.get(url, timeout=6.0)
        return self._parse(r.text, source="Google News")
    def _parse(self, rss_text, source):
        try:
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
        except Exception:
            return []

class NewsMasterAgent:
    def __init__(self):
        self.agents = [YahooNewsAgent(), MarketWatchAgent(), GoogleNewsAgent()]
        self.index = 0
    def get_news(self, ticker: str):
        for i in range(len(self.agents)):
            agent = self.agents[(self.index + i) % len(self.agents)]
            try:
                raw_news = agent.fetch(ticker)
                self.index = (self.index + 1) % len(self.agents)
                translated = []
                for n in raw_news:
                    try:
                        hebrew = translator.translate(n["headline"], src='en', dest='he').text
                        translated.append({**n, "headline_he": hebrew})
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
                print(f"Agent failed: {e}")
        return {"ticker": ticker, "count": 0, "items": [], "source": "None"}
