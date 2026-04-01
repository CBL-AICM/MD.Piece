"""
GPT-Researcher Integration Service for MD.Piece

Uses assafelovic/gpt-researcher to automatically collect medical research:
- PubMed / medical journal papers
- Health authority guidelines (CDC, WHO, Taiwan MOHW)
- Latest clinical research reports

Output: JSON research summaries with source URLs and excerpts,
usable as raw material for Stanford STORM article generation.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Character limits for output truncation
MAX_EXCERPT_LENGTH = 500

# Medical-specific source domains to prioritize
# These are used to guide GPT-Researcher when searching for authoritative medical content.
# Pass a subset as `source_urls` to restrict research to known trusted domains.
MEDICAL_SOURCES = [
    "pubmed.ncbi.nlm.nih.gov",
    "ncbi.nlm.nih.gov",
    "who.int",
    "cdc.gov",
    "nih.gov",
    "nejm.org",
    "thelancet.com",
    "bmj.com",
    "jamanetwork.com",
    "mayoclinic.org",
    "webmd.com",
    "healthline.com",
    "mohw.gov.tw",
    "cdc.gov.tw",
]


async def research_medical_topic(
    topic: str,
    report_type: str = "research_report",
    max_sources: int = 10,
) -> dict:
    """
    Research a medical topic using GPT-Researcher and return a structured report.

    Args:
        topic: Medical topic to research (e.g., "hypertension treatment guidelines 2024")
        report_type: Type of report - "research_report", "outline_report", or "resource_report"
        max_sources: Maximum number of sources to include

    Returns:
        dict with keys: topic, report, sources, report_type, source_count

    Raises:
        ImportError: If gpt-researcher is not installed
        RuntimeError: If the research process fails
    """
    try:
        from gpt_researcher import GPTResearcher
    except ImportError as exc:
        raise ImportError(
            "gpt-researcher not installed. Run: pip install gpt-researcher"
        ) from exc

    researcher = GPTResearcher(
        query=topic,
        report_type=report_type,
        report_source="web",
    )

    await researcher.conduct_research()
    report = await researcher.write_report()

    # Collect sources from research results
    sources = []
    research_context = researcher.get_research_sources()
    if research_context:
        for src in research_context[:max_sources]:
            if isinstance(src, dict):
                sources.append({
                    "url": src.get("url", ""),
                    "title": src.get("title", ""),
                    "content": src.get("raw_content", "")[:MAX_EXCERPT_LENGTH] if src.get("raw_content") else "",
                })
            elif isinstance(src, str):
                sources.append({"url": src, "title": "", "content": ""})

    return {
        "topic": topic,
        "report": report,
        "sources": sources,
        "report_type": report_type,
        "source_count": len(sources),
    }


async def collect_medical_sources(
    topic: str,
    max_sources: int = 10,
) -> dict:
    """
    Collect source URLs and excerpts for a medical topic without generating a full report.
    Useful as raw material input for Stanford STORM article generation.

    Args:
        topic: Medical topic to search
        max_sources: Maximum number of sources to collect

    Returns:
        dict with keys: topic, sources (list of {url, title, content}), source_count

    Raises:
        ImportError: If gpt-researcher is not installed
        RuntimeError: If source collection fails
    """
    result = await research_medical_topic(
        topic=topic,
        report_type="resource_report",
        max_sources=max_sources,
    )
    return {
        "topic": result["topic"],
        "sources": result["sources"],
        "source_count": result["source_count"],
    }
