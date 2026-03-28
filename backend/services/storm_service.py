"""
Stanford STORM 整合服務

使用 STORM 框架自動產生含引用的醫療衛教文章。
支援 STORM（全自動）與 Co-STORM（人機協作）兩種模式。
"""

import os
import logging
import tempfile
import json
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# STORM 輸出目錄
STORM_OUTPUT_DIR = os.environ.get(
    "STORM_OUTPUT_DIR",
    os.path.join(tempfile.gettempdir(), "storm_output"),
)


def _get_lm(model: Optional[str] = None, max_tokens: int = 4096):
    """建立 LitellmModel，預設使用 Claude。"""
    from knowledge_storm.lm import LitellmModel

    model = model or os.environ.get(
        "STORM_LLM_MODEL", "anthropic/claude-haiku-4-5-20251001"
    )
    return LitellmModel(model=model, max_tokens=max_tokens)


def _get_rm(search_engine: Optional[str] = None, top_k: int = 3):
    """建立檢索模組，根據可用 API key 自動選擇搜尋引擎。"""
    engine = search_engine or os.environ.get("STORM_SEARCH_ENGINE", "duckduckgo")

    if engine == "you" and os.environ.get("YDC_API_KEY"):
        from knowledge_storm.rm import YouRM
        return YouRM(ydc_api_key=os.environ["YDC_API_KEY"], k=top_k)

    if engine == "tavily" and os.environ.get("TAVILY_API_KEY"):
        from knowledge_storm.rm import TavilySearchRM
        return TavilySearchRM(
            tavily_search_api_key=os.environ["TAVILY_API_KEY"], k=top_k
        )

    if engine == "bing" and os.environ.get("BING_SEARCH_API_KEY"):
        from knowledge_storm.rm import BingSearch
        return BingSearch(
            bing_search_api_key=os.environ["BING_SEARCH_API_KEY"], k=top_k
        )

    if engine == "serper" and os.environ.get("SERPER_API_KEY"):
        from knowledge_storm.rm import SerperRM
        return SerperRM(serper_search_api_key=os.environ["SERPER_API_KEY"], k=top_k)

    # 預設使用 DuckDuckGo（免費，無需 API key）
    from knowledge_storm.rm import DuckDuckGoSearchRM
    return DuckDuckGoSearchRM(k=top_k)


def build_storm_configs():
    """建立 STORM 各階段所需的 LLM 設定。"""
    from knowledge_storm import STORMWikiLMConfigs

    lm_configs = STORMWikiLMConfigs()
    conv_lm = _get_lm(max_tokens=1024)
    qa_lm = _get_lm(max_tokens=1024)
    outline_lm = _get_lm(max_tokens=2048)
    article_lm = _get_lm(max_tokens=4096)
    polish_lm = _get_lm(max_tokens=4096)

    lm_configs.set_conv_simulator_lm(conv_lm)
    lm_configs.set_question_asker_lm(qa_lm)
    lm_configs.set_outline_gen_lm(outline_lm)
    lm_configs.set_article_gen_lm(article_lm)
    lm_configs.set_article_polish_lm(polish_lm)
    return lm_configs


def run_storm_research(
    topic: str,
    search_engine: Optional[str] = None,
    search_top_k: int = 3,
    max_conv_turn: int = 3,
    max_perspective: int = 3,
    do_polish: bool = True,
) -> dict:
    """
    執行 STORM 全自動研究流程。

    Args:
        topic: 研究主題（例如 "第二型糖尿病的飲食管理"）
        search_engine: 搜尋引擎（you/tavily/bing/serper/duckduckgo）
        search_top_k: 每次搜尋取前 K 筆結果
        max_conv_turn: 模擬對話輪數
        max_perspective: 專家觀點數量
        do_polish: 是否進行最終潤稿

    Returns:
        dict 包含 topic, article, outline, output_dir
    """
    from knowledge_storm import STORMWikiRunnerArguments, STORMWikiRunner

    output_dir = os.path.join(STORM_OUTPUT_DIR, topic.replace(" ", "_"))
    os.makedirs(output_dir, exist_ok=True)

    engine_args = STORMWikiRunnerArguments(
        output_dir=output_dir,
        max_conv_turn=max_conv_turn,
        max_perspective=max_perspective,
        search_top_k=search_top_k,
    )

    lm_configs = build_storm_configs()
    rm = _get_rm(search_engine=search_engine, top_k=search_top_k)

    runner = STORMWikiRunner(engine_args, lm_configs, rm)

    logger.info(f"開始 STORM 研究：{topic}")
    runner.run(
        topic=topic,
        do_research=True,
        do_generate_outline=True,
        do_generate_article=True,
        do_polish_article=do_polish,
    )
    runner.post_run()
    runner.summary()

    # 讀取產出
    result = {
        "topic": topic,
        "output_dir": output_dir,
        "article": None,
        "outline": None,
    }

    article_path = Path(output_dir) / topic.replace(" ", "_") / "storm_gen_article_polished.txt"
    if not article_path.exists():
        article_path = Path(output_dir) / topic.replace(" ", "_") / "storm_gen_article.txt"
    # 也嘗試直接在 output_dir 下找
    if not article_path.exists():
        for candidate in Path(output_dir).rglob("storm_gen_article*.txt"):
            article_path = candidate
            break

    if article_path.exists():
        result["article"] = article_path.read_text(encoding="utf-8")

    outline_path = Path(output_dir) / topic.replace(" ", "_") / "storm_gen_outline.txt"
    if not outline_path.exists():
        for candidate in Path(output_dir).rglob("storm_gen_outline*.txt"):
            outline_path = candidate
            break

    if outline_path.exists():
        result["outline"] = outline_path.read_text(encoding="utf-8")

    logger.info(f"STORM 研究完成：{topic}，文章長度={len(result.get('article') or '')}")
    return result


def build_costorm_configs():
    """建立 Co-STORM 所需的 LLM 設定。"""
    from knowledge_storm.collaborative_storm.engine import CollaborativeStormLMConfigs

    lm_config = CollaborativeStormLMConfigs()
    qa_lm = _get_lm(max_tokens=2048)
    discourse_lm = _get_lm(max_tokens=1024)
    polish_lm = _get_lm(max_tokens=2048)

    lm_config.set_question_answering_lm(qa_lm)
    lm_config.set_discourse_manage_lm(discourse_lm)
    lm_config.set_utterance_polishing_lm(polish_lm)
    return lm_config


# Co-STORM 工作階段管理
_costorm_sessions: dict = {}


def create_costorm_session(
    topic: str,
    session_id: Optional[str] = None,
    search_engine: Optional[str] = None,
    search_top_k: int = 3,
) -> dict:
    """
    建立 Co-STORM 協作式研究會話。

    Returns:
        dict 包含 session_id, topic, status
    """
    from knowledge_storm.collaborative_storm.engine import RunnerArgument, CoStormRunner
    import uuid

    session_id = session_id or str(uuid.uuid4())[:8]
    output_dir = os.path.join(STORM_OUTPUT_DIR, f"costorm_{session_id}")
    os.makedirs(output_dir, exist_ok=True)

    lm_config = build_costorm_configs()
    rm = _get_rm(search_engine=search_engine, top_k=search_top_k)

    runner_arg = RunnerArgument(
        topic=topic,
        retrieve_top_k=search_top_k,
        output_dir=output_dir,
    )

    runner = CoStormRunner(
        lm_config=lm_config,
        runner_argument=runner_arg,
        rm=rm,
    )
    runner.warm_start()

    _costorm_sessions[session_id] = {
        "runner": runner,
        "topic": topic,
        "output_dir": output_dir,
        "turns": [],
    }

    logger.info(f"Co-STORM 會話建立：{session_id} - {topic}")
    return {"session_id": session_id, "topic": topic, "status": "ready"}


def costorm_step(session_id: str, user_utterance: Optional[str] = None) -> dict:
    """
    推進 Co-STORM 一個對話步驟。

    Args:
        session_id: 會話 ID
        user_utterance: 使用者（醫師）輸入，None 則讓 AI 自主對話

    Returns:
        dict 包含 turn 資訊
    """
    session = _costorm_sessions.get(session_id)
    if not session:
        raise ValueError(f"找不到 Co-STORM 會話：{session_id}")

    runner = session["runner"]
    if user_utterance:
        conv_turn = runner.step(user_utterance=user_utterance)
    else:
        conv_turn = runner.step()

    turn_info = {
        "agent_name": getattr(conv_turn, "agent_name", "unknown"),
        "utterance": getattr(conv_turn, "utterance", str(conv_turn)),
        "turn_index": len(session["turns"]),
    }
    session["turns"].append(turn_info)
    return turn_info


def costorm_generate_report(session_id: str) -> dict:
    """
    生成 Co-STORM 最終報告。

    Returns:
        dict 包含 report 文字
    """
    session = _costorm_sessions.get(session_id)
    if not session:
        raise ValueError(f"找不到 Co-STORM 會話：{session_id}")

    runner = session["runner"]
    runner.knowledge_base.reorganize()
    report = runner.generate_report()

    return {
        "session_id": session_id,
        "topic": session["topic"],
        "report": report,
        "total_turns": len(session["turns"]),
    }


def costorm_close_session(session_id: str) -> dict:
    """關閉並清理 Co-STORM 會話。"""
    session = _costorm_sessions.pop(session_id, None)
    if not session:
        raise ValueError(f"找不到 Co-STORM 會話：{session_id}")
    return {"session_id": session_id, "status": "closed"}
