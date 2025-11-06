# ==============================================================
# 🗞️ News Agent + Auto Translation (Hebrew)
# ==============================================================

import re
from googletrans import Translator

translator = Translator()

@app.get("/news/{ticker}")
async def get_stock_news(ticker: str):
    """
    Returns recent news (Finnhub or Yahoo RSS) + Hebrew translation
    """
    ticker = ticker.upper().strip()
    news_list = []
    translated_items = []
    final_source = None

    # --- Primary: Finnhub ---
    if FINNHUB_API_KEY:
        try:
            url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from=2024-11-01&to=2025-11-06&token={FINNHUB_API_KEY}"
            res = httpx.get(url, timeout=6.0)
            data = res.json()
            for n in data[:8]:
                news_list.append({
                    "headline": n.get("headline"),
                    "source": n.get("source"),
                    "url": n.get("url"),
                    "datetime": datetime.utcfromtimestamp(n.get("datetime", 0)).strftime("%Y-%m-%d"),
                    "summary": n.get("summary", "")
                })
            final_source = "Finnhub"
        except Exception:
            pass

    # --- Fallback: Yahoo RSS ---
    if not news_list:
        try:
            rss_url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
            rss = httpx.get(rss_url, timeout=6.0).text
            import xml.etree.ElementTree as ET
            root = ET.fromstring(rss)
            for item in root.findall(".//item")[:8]:
                title = item.find("title").text
                link = item.find("link").text
                pubDate = item.find("pubDate").text
                news_list.append({
                    "headline": title,
                    "source": "Yahoo Finance",
                    "url": link,
                    "datetime": pubDate,
                    "summary": ""
                })
            final_source = "Yahoo Finance"
        except Exception:
            pass

    # --- Translation to Hebrew ---
    for n in news_list:
        try:
            headline_clean = re.sub(r'\s+', ' ', n["headline"]).strip()
            translated = translator.translate(headline_clean, src='en', dest='he').text
            translated_items.append({
                **n,
                "headline_he": translated,
            })
        except Exception:
            translated_items.append({**n, "headline_he": n["headline"]})

    return {
        "ticker": ticker,
        "count": len(translated_items),
        "items": translated_items,
        "source": final_s_
