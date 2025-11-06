# providers/yahoo_agent.py
# Yahoo Agent (sync) - one agent instance uses its own httpx.Client/session and headers
import time, random
import httpx

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]

def safe_get(d, *keys, default=None):
    cur = d
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur

def parse_chart_response(resp_json):
    try:
        chart = resp_json.get("chart", {})
        result = (chart.get("result") or [None])[0]
        if not result:
            return None
        ts = result.get("timestamp", [])
        indicators = result.get("indicators", {}) or {}
        quote = (indicators.get("quote") or [{}])[0]
        close = quote.get("close", [])
        high = quote.get("high", [])
        low = quote.get("low", [])
        open_ = quote.get("open", [])
        volume = quote.get("volume", [])
        meta = result.get("meta", {}) or {}
        return {
            "meta": {
                "symbol": meta.get("symbol"),
                "currency": meta.get("currency"),
                "instrumentType": meta.get("instrumentType"),
                "range": meta.get("dataGranularity") or None,
                "regularMarketPrice": meta.get("regularMarketPrice"),
            },
            "series": {
                "timestamp": ts,
                "close": close,
                "high": high,
                "low": low,
                "open": open_,
                "volume": volume
            }
        }
    except Exception:
        return None

def parse_quote_summary(resp_json):
    try:
        result = (resp_json.get("quoteSummary", {}) or {}).get("result", [None])[0]
        if not result:
            return {}
        out = {}
        # company + sector
        price_blk = result.get("price", {}) or {}
        asset = result.get("assetProfile", {}) or {}
        out["shortName"] = price_blk.get("shortName") or None
        out["longName"]  = price_blk.get("longName")  or None
        out["company_name"] = out["shortName"] or out["longName"]
        out["sector"] = asset.get("sector") or None
        # financials
        fin = result.get("financialData", {}) or {}
        sumdet = result.get("summaryDetail", {}) or {}
        dks = result.get("defaultKeyStatistics", {}) or {}

        out["currentPrice"]  = safe_get(fin, "currentPrice", "raw") or safe_get(price_blk, "regularMarketPrice", "raw") or price_blk.get("regularMarketPrice")
        out["previousClose"] = safe_get(price_blk, "regularMarketPreviousClose", "raw") or safe_get(price_blk, "previousClose", "raw") or price_blk.get("regularMarketPreviousClose")
        out["marketCap"] = safe_get(price_blk, "marketCap", "raw")
        out["trailingPE"] = safe_get(sumdet, "trailingPE", "raw") or safe_get(dks, "trailingPE", "raw")
        out["priceToSalesTrailing12Months"] = safe_get(fin, "priceToSalesTrailing12Months", "raw")
        out["pegRatio"] = safe_get(dks, "pegRatio", "raw")
        out["revenueGrowth"] = safe_get(fin, "revenueGrowth", "raw")
        out["earningsQuarterlyGrowth"] = safe_get(fin, "earningsQuarterlyGrowth", "raw")
        out["debtToEquity"] = safe_get(fin, "debtToEquity", "raw") or safe_get(dks, "debtToEquity", "raw")
        out["currentRatio"] = safe_get(fin, "currentRatio", "raw")
        out["profitMargins"] = safe_get(fin, "profitMargins", "raw") or safe_get(dks, "profitMargins", "raw")
        out["returnOnEquity"] = safe_get(fin, "returnOnEquity", "raw")
        out["dividendYield"] = safe_get(sumdet, "dividendYield", "raw")
        out["symbol"] = price_blk.get("symbol")
        return out
    except Exception:
        return {}

class YahooAgent:
    def __init__(self, id: int):
        self.id = id
        self.name = f"YahooAgent-{id}"
        self.cooldown_until = 0.0
        self.client = httpx.Client(timeout=8.0)
        self.client.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9"
        })

    def is_available(self):
        return time.time() >= (self.cooldown_until or 0)

    def set_cooldown(self, seconds=300):
        self.cooldown_until = time.time() + seconds

    def fetch(self, ticker: str):
        ticker = ticker.upper().strip()
        time.sleep(random.uniform(0.05, 0.25))  # jitter קטן

        # chart
        chart_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=6mo&interval=1d"
        try:
            r = self.client.get(chart_url)
            if r.status_code == 429:
                self.set_cooldown(300)
                raise Exception("RateLimit")
            chart_json = r.json()
            chart_parsed = parse_chart_response(chart_json)
        except httpx.HTTPError:
            chart_parsed = None
        except Exception as e:
            if "ratelimit" in str(e).lower():
                raise
            chart_parsed = None

        # quote summary
        qurl = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules=assetProfile,financialData,summaryDetail,defaultKeyStatistics,price"
        try:
            r2 = self.client.get(qurl)
            if r2.status_code == 429:
                self.set_cooldown(300)
                raise Exception("RateLimit")
            qjson = r2.json()
            q_parsed = parse_quote_summary(qjson)
        except httpx.HTTPError:
            q_parsed = {}
        except Exception as e:
            if "ratelimit" in str(e).lower():
                raise
            q_parsed = {}

        return {
            "provider": "yahoo",
            "agent": self.name,
            "raw_quote": q_parsed,
            "raw_chart": chart_parsed
        }
