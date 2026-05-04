"""
STORM / Co-STORM Integration Service for MD.Piece

Stanford STORM：多輪文獻搜尋 → 大綱生成 → 含引用的長篇研究文章
Co-STORM：醫師可介入的協作式研究策展

所有 LM 使用 Claude 模型，搜尋引擎預設 DuckDuckGo（免費無需 API key）。
"""

import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Import knowledge_storm ────────────────────────────────

try:
    from knowledge_storm import (
        STORMWikiRunnerArguments,
        STORMWikiRunner,
        STORMWikiLMConfigs,
    )
    from knowledge_storm.lm import ClaudeModel
    from knowledge_storm.rm import DuckDuckGoSearchRM, TavilySearchRM, SerperRM
    from knowledge_storm.collaborative_storm.engine import (
        CollaborativeStormLMConfigs,
        RunnerArgument,
        CoStormRunner,
    )
    from knowledge_storm.logging_wrapper import LoggingWrapper

    STORM_AVAILABLE = True
except ImportError:
    storm_path = Path(__file__).resolve().parents[2] / "storm"
    if storm_path.exists():
        sys.path.insert(0, str(storm_path))
        from knowledge_storm import (
            STORMWikiRunnerArguments, STORMWikiRunner, STORMWikiLMConfigs,
        )
        from knowledge_storm.lm import ClaudeModel
        from knowledge_storm.rm import DuckDuckGoSearchRM, TavilySearchRM, SerperRM
        from knowledge_storm.collaborative_storm.engine import (
            CollaborativeStormLMConfigs, RunnerArgument, CoStormRunner,
        )
        from knowledge_storm.logging_wrapper import LoggingWrapper
        STORM_AVAILABLE = True
    else:
        STORM_AVAILABLE = False
        logger.warning("knowledge-storm not found — STORM features disabled")


# ── Output directory ──────────────────────────────────────

STORM_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output" / "storm"
STORM_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ── Search engine helper ──────────────────────────────────

def _get_retriever(search_top_k: int = 5):
    """依可用 API key 選擇搜尋引擎，預設 DuckDuckGo（免費）"""
    if os.getenv("TAVILY_API_KEY"):
        return TavilySearchRM(
            tavily_search_api_key=os.getenv("TAVILY_API_KEY"),
            k=search_top_k,
            include_raw_content=True,
        )
    if os.getenv("SERPER_API_KEY"):
        return SerperRM(
            serper_search_api_key=os.getenv("SERPER_API_KEY"),
            query_params={"autocorrect": True, "num": 10, "page": 1},
        )
    return DuckDuckGoSearchRM(k=search_top_k, safe_search="On", region="wt-wt")


# ── Claude model configs ──────────────────────────────────

def _claude_kwargs():
    return {
        "api_key": os.getenv("ANTHROPIC_API_KEY"),
        "temperature": 1.0,
        "top_p": 0.9,
    }


# ══════════════════════════════════════════════════════════
#  STORM — 自動文獻研究 + 論文生成
# ══════════════════════════════════════════════════════════

def create_storm_runner(output_dir: str | None = None) -> STORMWikiRunner:
    """建立 STORM runner，用 Claude 模型做多輪文獻搜尋與文章生成"""
    if not STORM_AVAILABLE:
        raise RuntimeError("knowledge-storm 未安裝")

    out = output_dir or str(STORM_OUTPUT_DIR / "wiki")
    os.makedirs(out, exist_ok=True)

    lm_configs = STORMWikiLMConfigs()
    kw = _claude_kwargs()

    # 較便宜的模型做對話模擬，較強的模型做大綱與文章
    conv_simulator_lm = ClaudeModel(model="claude-haiku-4-5-20251001", max_tokens=500, **kw)
    question_asker_lm = ClaudeModel(model="claude-haiku-4-5-20251001", max_tokens=500, **kw)
    outline_gen_lm = ClaudeModel(model="claude-sonnet-4-6", max_tokens=400, **kw)
    article_gen_lm = ClaudeModel(model="claude-sonnet-4-6", max_tokens=700, **kw)
    article_polish_lm = ClaudeModel(model="claude-sonnet-4-6", max_tokens=4000, **kw)

    lm_configs.set_conv_simulator_lm(conv_simulator_lm)
    lm_configs.set_question_asker_lm(question_asker_lm)
    lm_configs.set_outline_gen_lm(outline_gen_lm)
    lm_configs.set_article_gen_lm(article_gen_lm)
    lm_configs.set_article_polish_lm(article_polish_lm)

    engine_args = STORMWikiRunnerArguments(
        output_dir=out,
        max_conv_turn=3,
        max_perspective=3,
        search_top_k=5,
        max_thread_num=3,
    )

    rm = _get_retriever(search_top_k=5)
    return STORMWikiRunner(engine_args, lm_configs, rm)


def run_storm_research(topic: str, output_dir: str | None = None) -> dict:
    """
    執行 STORM pipeline：多輪搜尋 → 大綱 → 含引用長篇文章

    回傳: { topic, report, outline, sources, output_path }
    """
    out = output_dir or str(STORM_OUTPUT_DIR / "wiki")
    try:
        runner = create_storm_runner(output_dir=out)
        runner.run(
            topic=topic,
            do_research=True,
            do_generate_outline=True,
            do_generate_article=True,
            do_polish_article=True,
        )
        runner.post_run()
        runner.summary()

        # 讀取生成的文件
        topic_dir = Path(out) / topic.replace(" ", "_").replace("/", "_")
        result = {"topic": topic, "output_path": str(topic_dir)}

        article_path = topic_dir / "storm_gen_article_polished.txt"
        if not article_path.exists():
            article_path = topic_dir / "storm_gen_article.txt"
        result["report"] = article_path.read_text(encoding="utf-8") if article_path.exists() else ""

        outline_path = topic_dir / "storm_gen_outline.txt"
        result["outline"] = outline_path.read_text(encoding="utf-8") if outline_path.exists() else ""

        sources_path = topic_dir / "url_to_info.json"
        if sources_path.exists():
            sources = json.loads(sources_path.read_text(encoding="utf-8"))
            result["sources"] = list(sources.keys()) if isinstance(sources, dict) else []
            result["source_count"] = len(result["sources"])
        else:
            result["sources"] = []
            result["source_count"] = 0

        return result

    except Exception as e:
        logger.error(f"STORM research failed for '{topic}': {e}")
        return {"topic": topic, "error": str(e)}


# ══════════════════════════════════════════════════════════
#  Co-STORM — 醫師協作式研究策展
# ══════════════════════════════════════════════════════════

def create_costorm_runner(topic: str) -> CoStormRunner:
    """建立 Co-STORM runner，支援醫師介入的協作研究"""
    if not STORM_AVAILABLE:
        raise RuntimeError("knowledge-storm 未安裝")

    lm_config = CollaborativeStormLMConfigs()
    kw = _claude_kwargs()

    qa_lm = ClaudeModel(model="claude-sonnet-4-6", max_tokens=1000, **kw)
    discourse_lm = ClaudeModel(model="claude-sonnet-4-6", max_tokens=500, **kw)
    polish_lm = ClaudeModel(model="claude-sonnet-4-6", max_tokens=2000, **kw)
    outline_lm = ClaudeModel(model="claude-sonnet-4-6", max_tokens=500, **kw)
    ask_lm = ClaudeModel(model="claude-haiku-4-5-20251001", max_tokens=300, **kw)
    kb_lm = ClaudeModel(model="claude-sonnet-4-6", max_tokens=1000, **kw)

    lm_config.set_question_answering_lm(qa_lm)
    lm_config.set_discourse_manage_lm(discourse_lm)
    lm_config.set_utterance_polishing_lm(polish_lm)
    lm_config.set_warmstart_outline_gen_lm(outline_lm)
    lm_config.set_question_asking_lm(ask_lm)
    lm_config.set_knowledge_base_lm(kb_lm)

    runner_arg = RunnerArgument(
        topic=topic,
        retrieve_top_k=10,
        max_search_queries=2,
        total_conv_turn=20,
        max_search_thread=5,
        max_search_queries_per_turn=3,
        warmstart_max_num_experts=3,
        warmstart_max_turn_per_experts=2,
        warmstart_max_thread=3,
        max_thread_num=5,
        max_num_round_table_experts=2,
        moderator_override_N_consecutive_answering_turn=3,
        node_expansion_trigger_count=10,
    )

    rm = _get_retriever(search_top_k=10)
    logging_wrapper = LoggingWrapper(lm_config)

    return CoStormRunner(
        lm_config=lm_config,
        runner_argument=runner_arg,
        logging_wrapper=logging_wrapper,
        rm=rm,
        callback_handler=None,
    )


def run_costorm_research(topic: str, doctor_inputs: list[str] | None = None) -> dict:
    """
    執行 Co-STORM：warm start → AI 對話輪 → 醫師輸入 → 產出報告

    Args:
        topic: 研究主題
        doctor_inputs: 醫師的觀點/問題列表（可選）

    回傳: { topic, report, conversation_log }
    """
    out_dir = STORM_OUTPUT_DIR / "costorm" / topic.replace(" ", "_").replace("/", "_")
    os.makedirs(out_dir, exist_ok=True)

    try:
        runner = create_costorm_runner(topic)
        runner.warm_start()

        conversation = []

        # AI 先進行 3 輪自主討論
        for _ in range(3):
            turn = runner.step()
            conversation.append({"role": turn.role, "utterance": turn.utterance})

        # 注入醫師觀點
        if doctor_inputs:
            for utterance in doctor_inputs:
                runner.step(user_utterance=utterance)
                conversation.append({"role": "doctor", "utterance": utterance})
                # AI 回應
                turn = runner.step()
                conversation.append({"role": turn.role, "utterance": turn.utterance})

        # 再進行 2 輪自主討論
        for _ in range(2):
            turn = runner.step()
            conversation.append({"role": turn.role, "utterance": turn.utterance})

        # 生成報告
        runner.knowledge_base.reorganize()
        report = runner.generate_report()

        # 儲存
        (out_dir / "report.md").write_text(report, encoding="utf-8")
        (out_dir / "conversation.json").write_text(
            json.dumps(conversation, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        instance_copy = runner.to_dict()
        (out_dir / "instance_dump.json").write_text(
            json.dumps(instance_copy, indent=2), encoding="utf-8"
        )

        return {
            "topic": topic,
            "report": report,
            "conversation": conversation,
            "output_path": str(out_dir),
        }

    except Exception as e:
        logger.error(f"Co-STORM research failed for '{topic}': {e}")
        return {"topic": topic, "error": str(e)}
