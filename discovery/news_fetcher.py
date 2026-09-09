import logging
import feedparser
import httpx
from app.config import settings
from discovery.normalizer import normalize
from discovery.verifier import verify_source
from utils.retry import with_retry

logger = logging.getLogger("autonomous_creator.discovery")

@with_retry(max_attempts=2, initial_delay=0.5, allowed_exceptions=(httpx.RequestError,))
def fetch_from_newsapi(query: str = "artificial intelligence OR LLM OR autonomous agent", api_key: str = "") -> list[dict]:
    """Fetches top tech articles from NewsAPI."""
    key = api_key or settings.NEWS_API_KEY
    if not key:
        logger.debug("No NEWS_API_KEY configured; skipping NewsAPI source.")
        return []
    
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "sortBy": "publishedAt",
        "pageSize": 15,
        "language": "en",
        "apiKey": key
    }
    
    with httpx.Client(timeout=6.0) as client:
        resp = client.get(url, params=params)
        if resp.status_code != 200:
            logger.warning(f"NewsAPI returned status {resp.status_code}: {resp.text[:100]}")
            return []
        
        data = resp.json()
        articles = data.get("articles", [])
        raw_items = []
        for a in articles:
            raw_items.append({
                "source": a.get("source", {}).get("name", "NewsAPI"),
                "url": a.get("url", ""),
                "title": a.get("title", ""),
                "summary": a.get("description", "") or a.get("content", ""),
                "published_at": a.get("publishedAt")
            })
        return raw_items


def fetch_from_rss(feed_urls: list[str]) -> list[dict]:
    """Fetches articles from a list of RSS feeds with individual error isolation."""
    items: list[dict] = []
    for feed_url in feed_urls:
        try:
            # feedparser can parse remote URLs or raw content
            feed = feedparser.parse(feed_url)
            source_title = feed.feed.get("title", "Tech RSS")
            
            for entry in feed.entries[:8]:  # Top 8 from each feed
                title = entry.get("title", "")
                link = entry.get("link", "")
                summary = entry.get("summary", "") or entry.get("description", "")
                pub_date = entry.get("published") or entry.get("updated")
                
                if title and link:
                    items.append({
                        "source": source_title,
                        "url": link,
                        "title": title,
                        "summary": summary,
                        "published_at": pub_date
                    })
        except Exception as e:
            logger.warning(f"Failed to parse RSS feed {feed_url}: {e}")
            continue
            
    return items


def fetch_all() -> list[dict]:
    """
    Main discovery orchestrator.
    Aggregates live NewsAPI and RSS entries and returns normalized items.

    Empty results are intentional: the pipeline must not manufacture stories
    when every live source is unavailable.
    """
    raw_collected: list[dict] = []
    
    # 1. NewsAPI
    try:
        api_items = fetch_from_newsapi()
        if api_items:
            raw_collected.extend(api_items)
            logger.info(f"Fetched {len(api_items)} items from NewsAPI.")
    except Exception as e:
        logger.warning(f"NewsAPI fetch error: {e}")
        
    # 2. RSS Feeds
    try:
        rss_items = fetch_from_rss(settings.RSS_FEEDS)
        if rss_items:
            raw_collected.extend(rss_items)
            logger.info(f"Fetched {len(rss_items)} items from RSS feeds.")
    except Exception as e:
        logger.warning(f"RSS fetch error: {e}")
        
    # Normalize all collected raw items
    normalized_items: list[dict] = []
    for raw in raw_collected:
        if raw.get("title") and raw.get("url"):
            norm = normalize(raw)
            if norm["title"] and norm["source_url"] and verify_source(norm["source_url"]):
                normalized_items.append(norm)
                
    return normalized_items
