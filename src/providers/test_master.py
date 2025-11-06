from src.providers.stockron_master_agent import MASTER_AGENT

print("🔸 Fetching financials for NVDA...")
data = MASTER_AGENT.fetch_financials("NVDA")
print("✅ Result:", data.get("source"), "| Price:", data.get("price"))

print("\n🗞️ Fetching news for NVDA...")
news = MASTER_AGENT.fetch_news("NVDA")
print("✅ News Source:", news.get("source"))
print("Top headline:", news["items"][0]["headline"] if news["count"] > 0 else "No news")
