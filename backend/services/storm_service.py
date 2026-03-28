"""
STORM Integration Service for MD.Piece

Uses Stanford STORM (knowledge-storm) to generate research reports
on medical topics with citations.

Three integration paths available:
  A. Submodule: import from ../storm/knowledge_storm
  B. Direct: this file wraps the pip package
  C. pip: `from knowledge_storm import STORMWikiRunnerArguments, STORMWikiRunner`
"""

import os
import sys
from pathlib import Path

# Try pip package first (C), fallback to submodule path (A)
try:
    from knowledge_storm import STORMWikiRunnerArguments, STORMWikiRunner, STORMWikiLMConfigs
except ImportError:
    # Fallback: add submodule to path
    storm_path = Path(__file__).resolve().parents[2] / "storm"
    if storm_path.exists():
        sys.path.insert(0, str(storm_path))
        from knowledge_storm import STORMWikiRunnerArguments, STORMWikiRunner, STORMWikiLMConfigs
    else:
        raise ImportError(
            "knowledge-storm not found. Install via: pip install knowledge-storm "
            "or ensure the storm submodule is initialized: git submodule update --init"
        )


def create_storm_runner(
    output_dir: str = "./storm_output",
    search_engine: str = "you",
) -> STORMWikiRunner:
    """Create a STORM runner configured for medical research."""
    lm_configs = STORMWikiLMConfigs()

    engine_kwargs = {
        "ydc_api_key": os.getenv("YDC_API_KEY", ""),
    }

    args = STORMWikiRunnerArguments(
        output_dir=output_dir,
        search_top_k=3,
        max_conv_turn=3,
        max_perspective=3,
    )

    runner = STORMWikiRunner(args, lm_configs, rm=None)
    return runner


async def research_medical_topic(topic: str, output_dir: str = "./storm_output") -> dict:
    """
    Research a medical topic using STORM and return the generated report.

    Args:
        topic: Medical topic to research (e.g., "hypertension treatment guidelines")
        output_dir: Directory to save output files

    Returns:
        dict with 'report' (str) and 'references' (list)
    """
    try:
        runner = create_storm_runner(output_dir=output_dir)
        runner.run(
            topic=topic,
            do_research=True,
            do_generate_outline=True,
            do_generate_article=True,
            do_polish_article=True,
        )
        runner.post_run()
        runner.summary()

        # Read generated article
        article_path = Path(output_dir) / topic.replace(" ", "_") / "storm_gen_article_polished.txt"
        report = article_path.read_text(encoding="utf-8") if article_path.exists() else "Report generation completed but file not found."

        return {"report": report, "topic": topic, "output_dir": output_dir}

    except Exception as e:
        return {"error": str(e), "topic": topic}
