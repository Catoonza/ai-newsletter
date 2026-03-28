"""
Fetches blog posts from AI provider RSS feeds.
No API key required — RSS is open and free.

Notes on broken/JS-rendered sites:
- Anthropic: no native RSS, use community-maintained feeds from github.com/Olshansk/rss-feeds
- OpenAI: no native RSS for research, use community feed; blog.rss.xml works natively
- Meta AI: no public RSS feed at all, use Meta Research feed instead
- Mistral: their /rss endpoint is broken; no known working feed, covered by NewsAPI instead
- Windsurf: community feed not maintained, removed
"""

import time
import datetime
import feedparser
from typing import List, Dict


RSS_FEEDS = [
    # ── Anthropic ─────────────────────────────────────────────────
    # JS-rendered site — use community-maintained feeds (updated hourly)
    # Source: https://github.com/Olshansk/rss-feeds
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
    # Native blog feed works; research site is JS-rendered so use community feed
    {
        "name": "OpenAI Blog",
        "url": "https://openai.com/blog/rss.xml",
        "category": "provider",
    },
    {
        "name": "OpenAI Research",
        "url": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_openai_research.xml",
        "category": "provider",
    },

    # ── Google DeepMind ───────────────────────────────────────────
    {
        "name": "Google DeepMind",
        "url": "https://deepmind.google/blog/rss.xml",
        "category": "provider",
    },
    {
        "name": "Google AI / Research",
        "url": "https://research.google/blog/rss/",
        "category": "provider",
    },

    # ── Meta ──────────────────────────────────────────────────────
    # ai.meta.com/blog has no RSS — use Meta Research blog instead
    {
        "name": "Meta Research Blog",
        "url": "https://research.facebook.com/feed/",
        "category": "provider",
    },
    # Meta's general engineering blog also covers AI heavily
    {
        "name": "Meta Engineering Blog",
        "url": "https://engineering.fb.com/feed/",
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

    # ── Cursor ────────────────────────────────────────────────────
    {
        "name": "Cursor Blog",
        "url": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_cursor.xml",
        "category": "tools",
    },

    # ── The Verge AI ─────────────────────────────────────────────
    {
        "name": "The Verge - AI",
        "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "category": "news",
    },

    # ── Ars Technica AI ───────────────────────────────────────────
    {
        "name": "Ars Technica - AI",
        "url": "https://feeds.arstechnica.com/arstechnica/technology-lab",
        "category": "news",
    },
]


def fetch_provider_blogs(start_date: datetime.datetime, end_date: datetime.datetime) -> List[Dict]:
    posts = []

    for feed_config in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_config["url"])

            # Warn if the feed came back completely empty
            if not feed.entries:
                print(f"   ⚠️  No entries from {feed_config['name']} ({feed_config['url']})")
                continue

            for entry in feed.entries:
                # Parse published date — try multiple fields
                published = None
                for date_field in ["published_parsed", "updated_parsed"]:
                    val = getattr(entry, date_field, None)
                    if val:
                        try:
                            published = datetime.datetime.fromtimestamp(time.mktime(val))
                        except (OverflowError, OSError):
                            pass
                        break

                if not published:
                    continue
                if not (start_date <= published <= end_date):
                    continue

                posts.append({
                    "source": "rss",
                    "provider": feed_config["name"],
                    "category": feed_config["category"],
                    "title": entry.get("title", "").strip(),
                    "summary": entry.get("summary", "")[:500],
                    "url": entry.get("link", ""),
                    "published_at": published.isoformat(),
                })

        except Exception as e:
            print(f"   ⚠️  RSS error for {feed_config['name']}: {e}")

    posts.sort(key=lambda x: x["published_at"], reverse=True)
    return posts
