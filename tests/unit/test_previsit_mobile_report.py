"""診前報告手機版回歸測試（純解析 frontend/js/app.js，不依賴瀏覽器）。

WHY：手機版「立即產生診前報告」的醫師分頁渲染進 #mobile-pv-doctor，但報告內容
（串流摘要 / 非串流 fallback）原本只寫進 desktop-only 的 #pv-report-body，導致
手機版點按鈕後醫師分頁停在佔位字「點上方『立即產生診前報告』生成醫師版精簡資訊」，
看起來毫無反應。

修法是把報告 HTML 透過 _pvSetReportHtml() 同步寫進兩個容器。本測試鎖住這個行為：
若日後有人改回只寫 #pv-report-body（或讓 _pvSetReportHtml 不再更新手機分頁），
這支測試就會失敗。
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP_JS = ROOT / "frontend" / "js" / "app.js"


def _read() -> str:
    return APP_JS.read_text(encoding="utf-8")


def _func_body(src: str, name: str) -> str:
    """以大括號配對取出某個 function 的完整原始碼（含 async）。"""
    m = re.search(r"(?:async\s+)?function\s+" + re.escape(name) + r"\s*\(", src)
    assert m, f"找不到函式 {name}"
    i = src.index("{", m.start())
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[m.start():j + 1]
    raise AssertionError(f"{name} 大括號未配對")


def test_helper_mirrors_report_into_mobile_doctor_tab():
    """_pvSetReportHtml 必須同時更新桌機 body 與手機醫師分頁。"""
    body = _func_body(_read(), "_pvSetReportHtml")
    assert "pv-report-body" in body, "_pvSetReportHtml 應更新桌機 #pv-report-body"
    assert "mobile-pv-doctor" in body, (
        "_pvSetReportHtml 應同步更新手機 #mobile-pv-doctor，否則手機版報告毫無反應"
    )
    # 兩個容器都要真的被指派 innerHTML（而非只取 reference）
    assert body.count(".innerHTML") >= 2, "兩個容器都要寫入 innerHTML"


@pytest.mark.parametrize(
    "func",
    [
        "previsitStreamReport",     # SSE 串流逐字渲染
        "previsitRenderReport",     # 非串流 /monthly fallback
        "previsitRenderReportError",  # 連線失敗
        "previsitReload",           # 點「立即產生診前報告」的進入點
    ],
)
def test_report_paths_route_through_mirror(func):
    """所有渲染報告內容的路徑都要經過 _pvSetReportHtml，報告才會出現在手機分頁。"""
    body = _func_body(_read(), func)
    assert "_pvSetReportHtml(" in body, (
        f"{func} 必須透過 _pvSetReportHtml() 渲染報告，否則手機醫師分頁不會更新"
    )


def test_no_report_content_written_desktop_only():
    """report 內容不得繞過 mirror 直接寫進 #pv-report-body（會漏掉手機分頁）。

    唯一允許出現 pv-report-body 的 innerHTML 指派位置是 _pvSetReportHtml 內部。
    """
    src = _read()
    helper = _func_body(src, "_pvSetReportHtml")
    src_without_helper = src.replace(helper, "")
    # 在不含 helper 的原始碼裡，不該再有把值寫進「以 pv-report-body 取得的元素」的指派。
    # 用一個寬鬆但有效的代理：直接抓 bodyEl.innerHTML = 之類的賦值已被移除。
    leaked = re.findall(r"document\.getElementById\('pv-report-body'\)\.innerHTML\s*=", src_without_helper)
    assert not leaked, "report 內容不應在 _pvSetReportHtml 之外直接寫進 #pv-report-body"
