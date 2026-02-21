"""
AI Weekly Newsletter Generator
Fetches data from multiple sources and uses Claude to summarise into a newsletter.
"""

import os
import json
import datetime
from collectors.news import fetch_ai_news
from collectors.rss import fetch_provider_blogs
from collectors.arxiv import fetch_arxiv_papers
from collectors.twitter import fetch_twitter_posts
from summariser import generate_newsletter
from exporter import save_newsletter


def main():
    print("=" * 60)
    print("AI Weekly Newsletter Generator")
    print("=" * 60)

    # Date range: last 7 days
    end_date = datetime.datetime.utcnow()
    start_date = end_date - datetime.timedelta(days=7)

    print(f"\nFetching data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}\n")

    # ── 1. Collect all data ──────────────────────────────────────
    print("📰 Fetching AI industry news...")
    news = fetch_ai_news(start_date, end_date)
    print(f"   → {len(news)} articles found")

    print("📡 Fetching AI provider blog posts...")
    blog_posts = fetch_provider_blogs(start_date, end_date)
    print(f"   → {len(blog_posts)} posts found")

    print("🔬 Fetching arXiv papers...")
    papers = fetch_arxiv_papers(start_date, end_date)
    print(f"   → {len(papers)} papers found")

    print("🐦 Fetching Twitter/X posts...")
    tweets = fetch_twitter_posts(start_date, end_date)
    print(f"   → {len(tweets)} tweets found")

    # ── 2. Bundle all collected data ─────────────────────────────
    collected_data = {
        "date_range": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "news_articles": news,
        "blog_posts": blog_posts,
        "arxiv_papers": papers,
        "tweets": tweets,
    }

    # Save raw data for debugging / archiving
    raw_path = f"output/raw_{end_date.strftime('%Y%m%d')}.json"
    os.makedirs("output", exist_ok=True)
    with open(raw_path, "w") as f:
        json.dump(collected_data, f, indent=2, default=str)
    print(f"\n💾 Raw data saved to {raw_path}")

    # ── 3. Summarise with Claude ─────────────────────────────────
    print("\n🤖 Generating newsletter with Claude...")
    newsletter_md = generate_newsletter(collected_data)

    # ── 4. Save final newsletter ─────────────────────────────────
    output_path = save_newsletter(newsletter_md, end_date)
    print(f"\n✅ Newsletter saved to {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
