"""時程防漂移：後端排程天數必須與前端時程窗格一致（規則 7：別讓兩份定義各走各的）。

時程在兩處各寫一份——後端 backend/routers/surveys.py 的 STUDY_REMINDER_OFFSETS／
FU48_OFFSET_DAYS（決定提醒何時推），前端 frontend/js/app.js 的 STUDY_WINDOWS／
STUDY_FU48_FROM_DAYS（決定 hub 何時顯示該填）。兩邊只要漂移，就會出現「提醒響了
但 hub 沒顯示」或反過來的鬼打牆。這個測試在任一邊被改動而沒同步時直接 fail（規則 9：
測的是『為什麼要一致』，不是單純跑得過）。
"""
import re
from pathlib import Path

from backend.routers.surveys import FU48_OFFSET_DAYS, STUDY_REMINDER_OFFSETS

APP_JS = Path(__file__).resolve().parents[2] / "frontend" / "js" / "app.js"


def _frontend_windows() -> dict:
    """從 app.js 抓 STUDY_WINDOWS 的 {tp: from} 對應。"""
    src = APP_JS.read_text(encoding="utf-8")
    block = re.search(r"var STUDY_WINDOWS\s*=\s*\[(.*?)\];", src, re.DOTALL)
    assert block, "app.js 找不到 STUDY_WINDOWS（前端時程窗格定義可能被移動或改名）"
    out = {}
    for tp, frm in re.findall(r"tp:\s*'([^']+)'[^}]*?from:\s*(\d+)", block.group(1)):
        out[tp] = int(frm)
    assert out, "STUDY_WINDOWS 解析不到任何窗格"
    return out


def _frontend_const(name: str) -> int:
    src = APP_JS.read_text(encoding="utf-8")
    m = re.search(r"var\s+" + re.escape(name) + r"\s*=\s*(\d+)\s*;", src)
    assert m, f"app.js 找不到常數 {name}"
    return int(m.group(1))


def test_reminder_offsets_match_frontend_window_starts():
    # 後端在第 N 天推提醒，前端該時點的窗格就必須從第 N 天開始；否則提醒與顯示對不上。
    windows = _frontend_windows()
    for tp, day in STUDY_REMINDER_OFFSETS.items():
        assert tp in windows, f"後端排了 {tp} 提醒，但前端 STUDY_WINDOWS 沒有對應窗格"
        assert windows[tp] == day, (
            f"{tp} 漂移：後端第 {day} 天推提醒，前端窗格卻從第 {windows[tp]} 天開始")


def test_fu48_offset_matches_frontend_window_start():
    # 回診後回饋：後端在回診 +FU48_OFFSET_DAYS 推提醒，前端 FU48 視窗也要從同一天起算。
    assert FU48_OFFSET_DAYS == _frontend_const("STUDY_FU48_FROM_DAYS"), (
        "FU48 漂移：後端排程天數與前端 STUDY_FU48_FROM_DAYS 不一致")
