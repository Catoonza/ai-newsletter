"""
Fetches blog posts from AI provider RSS feeds.
No API key required — RSS is open and free.
"""

import datetime
import feedparser
from typing import List, Dict


# Add or remove feeds here as needed
RSS_FEEDS = [
    # Anthropic
    {
        "name": "Anthropic",
        "url": "https://www.anthropic.com/news/rss.xml",
        "category": "provider",
    },
    # OpenAI
    {
        "name": "OpenAI Blog",
        "url": "https://openai.com/blog/rss.xml",
        "category": "provider",
    },
    # Google DeepMind
    {
        "name": "Google DeepMind",
        "url": "https://deepmind.google/blog/rss.xml",
        "category": "provider",
    },
    # Google AI Blog
    {
        "name": "Google AI Blog",
        "url": "https://blog.research.google/feeds/posts/default",
        "category": "provider",
    },
    # Mistral
    {
        "name": "Mistral AI",
        "url": "https://mistral.ai/news/rss",
        "category": "provider",
    },
    # Meta AI
    {
        "name": "Meta AI",
        "url": "https://ai.meta.com/blog/rss/",
        "category": "provider",
    },
    # Hugging Face
    {
        "name": "Hugging Face Blog",
        "url": "https://huggingface.co/blog/feed.xml",
        "category": "community",
    },
    # Microsoft Research
    {
        "name": "Microsoft Research AI",
        "url": "https://www.microsoft.com/en-us/research/feed/",
        "category": "provider",
    },
    # AWS Machine Learning Blog
    {
        "name": "AWS Machine Learning Blog",
        "url": "https://aws.amazon.com/blogs/machine-learning/feed/",
        "category": "provider",
    },
    # NVIDIA Technical Blog
    {
        "name": "NVIDIA Technical Blog",
        "url": "https://developer.nvidia.com/blog/feed/",
        "category": "provider",
    },
    # Cohere
    {
        "name": "Cohere Blog",
        "url": "https://cohere.com/blog/rss",
        "category": "provider",
    },
]


def fetch_provider_blogs(start_date: datetime.datetime, end_date: datetime.datetime) -> List[Dict]:
    posts = []

    for feed_config in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_config["url"])

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
