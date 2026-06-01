"""穿戴裝置雲端同步 — 廠商 OAuth 連接器（參考實作：Fitbit）。

依《睡眠紀錄模組 開發規格》的 source=imported 來源：透過廠商雲端 Web API
（OAuth 2.0）把使用者的睡眠紀錄拉進來，映射成 sleep_sessions 一列後存後台。

設計邊界（與 sleep_pipeline / sleep router 一致）：
  - 純記錄與確定性轉換（規則 5），不下診斷、不給建議、不呼叫 LLM。
  - OAuth token 屬機密：client_secret 只放環境變數、token 只存後端 DB，
    絕不外流到前端。

擴充點：Oura / Withings / Garmin 可比照本檔的 (build_authorize_url /
exchange_code / refresh / fetch_sleep / map_*_to_session) 五段結構新增，
sleep router 的端點再加對應 provider 分支即可。

可在此環境驗證的部分：map_fitbit_sleep_to_session（純函式，見 tests）。
無法在此環境驗證的部分（規則 12）：真正的 OAuth 往返與 Fitbit API 回應，
需在部署環境設定 FITBIT_CLIENT_ID / FITBIT_CLIENT_SECRET 並完成一次授權。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

try:
    import httpx
except ImportError:  # pragma: no cover - httpx 在本專案經 supabase/main 已可用
    httpx = None


# ── Fitbit 設定（全部來自環境變數，不寫死機密）──────────────

FITBIT_CLIENT_ID = os.getenv("FITBIT_CLIENT_ID", "")
FITBIT_CLIENT_SECRET = os.getenv("FITBIT_CLIENT_SECRET", "")
# 必須與 Fitbit 開發者後台註冊的 Redirect URI 完全一致。
FITBIT_REDIRECT_URI = os.getenv(
    "FITBIT_REDIRECT_URI",
    "https://www.mdpiece.life/sleep/connect/fitbit/callback",
)
FITBIT_SCOPE = "sleep"

_AUTHORIZE_URL = "https://www.fitbit.com/oauth2/authorize"
_TOKEN_URL = "https://api.fitbit.com/oauth2/token"
_SLEEP_RANGE_URL = "https://api.fitbit.com/1.2/user/-/sleep/date/{start}/{end}.json"

PROVIDER = "fitbit"


def is_configured() -> bool:
    """是否已備齊可啟動 OAuth 的設定（規則 12：沒設好就 loud-fail，不假裝能連）。"""
    return bool(FITBIT_CLIENT_ID and FITBIT_CLIENT_SECRET)


# ── state 簽章（防 CSRF：未持有 client_secret 者無法偽造 user_id）──

def make_state(user_id: str) -> str:
    """state = user_id.sig，sig 為 HMAC-SHA256(user_id, client_secret) 前 16 碼。

    serverless 無 session 可存，故把 user_id 帶在 state 並用 client_secret 簽章；
    callback 端驗章，攻擊者沒有 secret 就無法把自己的 Fitbit 掛到他人 user_id。
    """
    sig = hmac.new(
        FITBIT_CLIENT_SECRET.encode(), user_id.encode(), hashlib.sha256
    ).hexdigest()[:16]
    return f"{user_id}.{sig}"


def parse_state(state: str) -> Optional[str]:
    """驗 state 簽章，通過回 user_id，否則回 None。"""
    if not state or "." not in state:
        return None
    user_id, _, sig = state.rpartition(".")
    expected = hmac.new(
        FITBIT_CLIENT_SECRET.encode(), user_id.encode(), hashlib.sha256
    ).hexdigest()[:16]
    return user_id if hmac.compare_digest(sig, expected) else None


# ── OAuth 三段 ─────────────────────────────────────────────

def build_authorize_url(user_id: str) -> str:
    """產生 Fitbit 授權頁 URL（前端據此導向；不含任何機密）。"""
    params = {
        "response_type": "code",
        "client_id": FITBIT_CLIENT_ID,
        "scope": FITBIT_SCOPE,
        "redirect_uri": FITBIT_REDIRECT_URI,
        "state": make_state(user_id),
    }
    return f"{_AUTHORIZE_URL}?{urlencode(params)}"


def _basic_auth_header() -> dict:
    raw = f"{FITBIT_CLIENT_ID}:{FITBIT_CLIENT_SECRET}".encode()
    return {"Authorization": "Basic " + base64.b64encode(raw).decode()}


def _post_token(data: dict) -> dict:
    """打 Fitbit token endpoint，回標準化後的 token dict（含 expires_at）。"""
    if httpx is None:
        raise RuntimeError("httpx 不可用，無法呼叫 Fitbit token endpoint")
    headers = {**_basic_auth_header(), "Content-Type": "application/x-www-form-urlencoded"}
    r = httpx.post(_TOKEN_URL, headers=headers, data=data, timeout=15.0)
    if r.status_code >= 400:
        logger.error("Fitbit token 失敗 %s — %s", r.status_code, r.text)
        raise RuntimeError(f"Fitbit token endpoint 回 {r.status_code}")
    tok = r.json()
    expires_in = int(tok.get("expires_in", 28800))
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    return {
        "access_token": tok.get("access_token"),
        "refresh_token": tok.get("refresh_token"),
        "scope": tok.get("scope", FITBIT_SCOPE),
        "expires_at": expires_at.isoformat(),
    }


def exchange_code(code: str) -> dict:
    """授權碼換 token（callback 用）。"""
    return _post_token({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": FITBIT_REDIRECT_URI,
        "client_id": FITBIT_CLIENT_ID,
    })


def refresh(refresh_token: str) -> dict:
    """refresh_token 換新 token（同步前 token 過期時用）。"""
    return _post_token({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    })


# ── 抓睡眠資料 ─────────────────────────────────────────────

def fetch_sleep(access_token: str, start_date: str, end_date: str) -> list[dict]:
    """抓 [start_date, end_date]（YYYY-MM-DD）區間的睡眠 log，回 Fitbit `sleep` 陣列。"""
    if httpx is None:
        raise RuntimeError("httpx 不可用，無法呼叫 Fitbit sleep API")
    url = _SLEEP_RANGE_URL.format(start=start_date, end=end_date)
    r = httpx.get(url, headers={"Authorization": f"Bearer {access_token}"}, timeout=15.0)
    if r.status_code >= 400:
        logger.error("Fitbit sleep 抓取失敗 %s — %s", r.status_code, r.text)
        raise RuntimeError(f"Fitbit sleep API 回 {r.status_code}")
    return r.json().get("sleep", []) or []


# ── 純映射：Fitbit sleep log → sleep_sessions 列（可單測，規則 9）──

def _parse_fitbit_dt(s: str) -> datetime:
    """Fitbit 時間多為無時區的本地 ISO（含毫秒），容錯解析。"""
    s = (s or "").replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.fromisoformat(s.split(".")[0])


def _awakenings_count(levels: dict) -> int:
    """夜醒次數：stages 版用 wake.count、classic 版用 awake.count，缺則 0。"""
    summary = (levels or {}).get("summary", {}) or {}
    for key in ("wake", "awake"):
        node = summary.get(key)
        if isinstance(node, dict) and node.get("count") is not None:
            return int(node["count"])
    return 0


def map_fitbit_sleep_to_session(log: dict, user_id: str) -> dict:
    """把一筆 Fitbit sleep log 映射成 sleep_sessions 列（source=imported）。

    確定性轉換，對應關係（驗收見 tests/unit/test_wearable_sync.py）：
      bed_time            ← startTime
      sleep_onset         ← startTime + minutesToFallAsleep
      wake_time           ← endTime
      total_sleep_minutes ← minutesAsleep
      time_in_bed_minutes ← timeInBed
      sleep_efficiency    ← efficiency / 100（夾在 0–1）
      waso_minutes        ← minutesAwake
      awakenings_count    ← levels.summary.wake|awake.count
    """
    start = _parse_fitbit_dt(log.get("startTime"))
    end = _parse_fitbit_dt(log.get("endTime"))
    to_fall_asleep = int(log.get("minutesToFallAsleep", 0) or 0)
    onset = start + timedelta(minutes=to_fall_asleep)

    efficiency = log.get("efficiency")
    sleep_efficiency = None
    if efficiency is not None:
        sleep_efficiency = max(0.0, min(1.0, round(float(efficiency) / 100.0, 4)))

    return {
        "user_id": user_id,
        "bed_time": start.isoformat(),
        "sleep_onset": onset.isoformat(),
        "wake_time": end.isoformat(),
        "out_of_bed_time": None,
        "total_sleep_minutes": int(log.get("minutesAsleep", 0) or 0),
        "time_in_bed_minutes": int(log.get("timeInBed", 0) or 0),
        "sleep_efficiency": sleep_efficiency,
        "waso_minutes": int(log.get("minutesAwake", 0) or 0),
        "awakenings_count": _awakenings_count(log.get("levels", {})),
        "source": "imported",
        "is_edited": False,
    }
