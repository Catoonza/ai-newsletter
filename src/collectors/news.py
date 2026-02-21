"""
Fetches AI industry news from NewsAPI.
Free tier: 100 requests/day, articles from last 30 days.
"""

import os
import requests
import datetime
from typing import List, Dict


# Queries to run — each uses one API request
SEARCH_QUERIES = [
    "artificial intelligence industry",
    "machine learning enterprise",
    "AI regulation policy",
    "generative AI business",
    "large language model",
]


def fetch_ai_news(start_date: datetime.datetime, end_date: datetime.datetime) -> List[Dict]:
    api_key = os.environ.get("NEWSAPI_KEY")
    if not api_key:
        print("   ⚠️  NEWSAPI_KEY not set — skipping news fetch")
        return []

    articles = []
    seen_urls = set()

    for query in SEARCH_QUERIES:
        try:
            response = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "from": start_date.strftime("%Y-%m-%d"),
                    "to": end_date.strftime("%Y-%m-%d"),
                    "language": "en",
                    "sortBy": "relevancy",
                    "pageSize": 10,
                    "apiKey": api_key,
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            for article in data.get("articles", []):
                url = article.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # Skip removed/paywalled articles
                if article.get("title") == "[Removed]":
                    continue

                articles.append({
                    "source": "newsapi",
                    "title": article.get("title", ""),
                    "description": article.get("description", ""),
                    "url": url,
                    "published_at": article.get("publishedAt", ""),
                    "source_name": article.get("source", {}).get("name", ""),
                })

        except Exception as e:
            print(f"   ⚠️  NewsAPI error for query '{query}': {e}")

    return articles
