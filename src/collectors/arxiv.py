"""
Fetches recent AI/ML papers from arXiv using their free public API.
No API key required.

Categories covered:
  cs.AI  — Artificial Intelligence
  cs.LG  — Machine Learning
  cs.CL  — Computation and Language (NLP)
  cs.CV  — Computer Vision
  stat.ML — Statistics / Machine Learning
"""

import datetime
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict


ARXIV_API_URL = "http://export.arxiv.org/api/query"

CATEGORIES = [
    "cs.AI",
    "cs.LG",
    "cs.CL",
    "cs.CV",
    "stat.ML",
]

# Max papers per category (keep total manageable for the LLM)
MAX_PER_CATEGORY = 15


def fetch_arxiv_papers(start_date: datetime.datetime, end_date: datetime.datetime) -> List[Dict]:
    papers = []
    seen_ids = set()

    for category in CATEGORIES:
        try:
            # arXiv search query — filter by category and submission date
            query = f"cat:{category}"

            params = urllib.parse.urlencode({
                "search_query": query,
                "start": 0,
                "max_results": MAX_PER_CATEGORY,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            })

            url = f"{ARXIV_API_URL}?{params}"
            with urllib.request.urlopen(url, timeout=15) as response:
                xml_data = response.read()

            root = ET.fromstring(xml_data)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall("atom:entry", ns):
                # Parse ID
                paper_id = entry.find("atom:id", ns)
                paper_id = paper_id.text.strip() if paper_id is not None else ""

                if paper_id in seen_ids:
                    continue
                seen_ids.add(paper_id)

                # Parse published date
                published_el = entry.find("atom:published", ns)
                if published_el is None:
                    continue

                published_str = published_el.text.strip()
                try:
                    published = datetime.datetime.strptime(
                        published_str, "%Y-%m-%dT%H:%M:%SZ"
                    )
                except ValueError:
                    continue

                # Filter to last 7 days
                if not (start_date <= published <= end_date):
                    continue

                # Parse authors
                authors = []
                for author in entry.findall("atom:author", ns):
                    name = author.find("atom:name", ns)
                    if name is not None:
                        authors.append(name.text.strip())

                # Parse title and abstract
                title_el = entry.find("atom:title", ns)
                summary_el = entry.find("atom:summary", ns)

                title = title_el.text.strip().replace("\n", " ") if title_el is not None else ""
                abstract = summary_el.text.strip().replace("\n", " ") if summary_el is not None else ""

                # Parse categories
                paper_cats = [
                    tag.get("term", "")
                    for tag in entry.findall("atom:category", ns)
                ]

                papers.append({
                    "source": "arxiv",
                    "id": paper_id,
                    "title": title,
                    "authors": authors[:5],  # First 5 authors
                    "abstract": abstract[:600],  # Cap for LLM context
                    "categories": paper_cats,
                    "primary_category": category,
                    "url": paper_id,  # arXiv ID URL is the link
                    "published_at": published.isoformat(),
                })

        except Exception as e:
            print(f"   ⚠️  arXiv error for {category}: {e}")

    # Sort by date descending
    papers.sort(key=lambda x: x["published_at"], reverse=True)
    return papers
