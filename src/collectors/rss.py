"""
Fetches blog posts from AI provider RSS feeds.
No API key required — RSS is open and free.

NOTE ON ANTHROPIC & OPENAI:
Their sites are JavaScript-rendered and have no native RSS feed.
We use community-maintained feeds hosted on GitHub (updated hourly via Actions)
that scrape these sites. Source: https://github.com/Olshansk/rss-feeds
"""

import datetime
import feedparser
from typing import List, Dict


RSS_FEEDS = [
    # ── Anthropic ─────────────────────────────────────────────────
    # Community-maintained feeds (JS-rendered site, no native RSS)
    {
        "name": "Anthropic News",
        "url": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml",
        "category": "provider",
    },
    {
        "name": "Anthropic Engineering",
        "url": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_engineering.xml",
        "category": "provider",
    },
    {
        "name": "Anthropic Research",
        "url": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_research.xml",
        "category": "provider",
    },

    # ── OpenAI ────────────────────────────────────────────────────
    # Community-maintained feed (JS-rendered site, no native RSS)
    {
        "name": "OpenAI Research",
        "url": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_openai_research.xml",
        "category": "provider",
    },
    # OpenAI does also have a native blog feed
    {
        "name": "OpenAI Blog",
        "url": "https://openai.com/blog/rss.xml",
        "category": "provider",
    },

    # ── Google DeepMind ───────────────────────────────────────────
    {
        "name": "Google DeepMind",
        "url": "https://deepmind.google/blog/rss.xml",
        "category": "provider",
    },
    {
        "name": "Google AI Blog",
        "url": "https://blog.research.google/feeds/posts/default",
        "category": "provider",
    },

    # ── Mistral ───────────────────────────────────────────────────
    {
        "name": "Mistral AI",
        "url": "https://mistral.ai/news/rss",
        "category": "provider",
    },

    # ── Meta ──────────────────────────────────────────────────────
    {
        "name": "Meta AI",
        "url": "https://ai.meta.com/blog/rss/",
        "category": "provider",
    },

    # ── Hugging Face ──────────────────────────────────────────────
    {
        "name": "Hugging Face Blog",
        "url": "https://huggingface.co/blog/feed.xml",
        "category": "community",
    },

    # ── Microsoft ─────────────────────────────────────────────────
    {
        "name": "Microsoft Research AI",
        "url": "https://www.microsoft.com/en-us/research/feed/",
        "category": "provider",
    },

    # ── AWS ───────────────────────────────────────────────────────
    {
        "name": "AWS Machine Learning Blog",
        "url": "https://aws.amazon.com/blogs/machine-learning/feed/",
        "category": "provider",
    },

    # ── NVIDIA ────────────────────────────────────────────────────
    {
        "name": "NVIDIA Technical Blog",
        "url": "https://developer.nvidia.com/blog/feed/",
        "category": "provider",
    },

    # ── AI Coding Tools ───────────────────────────────────────────
    {
        "name": "Cursor Blog",
        "url": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_cursor.xml",
        "category": "tools",
    },
    {
        "name": "Windsurf Blog",
        "url": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_windsurf.xml",
        "category": "tools",
    },
]


def fetch_provider_blogs(start_date: datetime.datetime, end_date: datetime.datetime) -> List[Dict]:
    posts = []

    for feed_config in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_config["url"])

            # Warn if the feed returned nothing at all (likely a dead URL)
            if feed.bozo and not feed.entries:
                print(f"   ⚠️  Empty/broken feed for {feed_config['name']}: {feed_config['url']}")
                continue

            for entry in feed.entries:
                # Parse published date
                published = None
                for date_field in ["published_parsed", "updated_parsed"]:
                    if hasattr(entry, date_field) and getattr(entry, date_field):
                        import time
                        published = datetime.datetime.fromtimestamp(
                            time.mktime(getattr(entry, date_field))
                        )
                        break

                # Skip if no date or outside range
                if not published:
                    continue
                if not (start_date <= published <= end_date):
                    continue

                posts.append({
                    "source": "rss",
                    "provider": feed_config["name"],
                    "category": feed_config["category"],
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", "")[:500],  # Cap length
                    "url": entry.get("link", ""),
                    "published_at": published.isoformat(),
                })

        except Exception as e:
            print(f"   ⚠️  RSS error for {feed_config['name']}: {e}")

    # Sort by date descending
    posts.sort(key=lambda x: x["published_at"], reverse=True)
    return posts
