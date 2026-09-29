import io
import logging
import time

import requests

import config

logger = logging.getLogger(__name__)

API_BASE = "https://open.tiktokapis.com/v2"
CREATOR_INFO_URL = f"{API_BASE}/post/publish/creator_info/query/"
VIDEO_INIT_URL = f"{API_BASE}/post/publish/video/init/"
STATUS_URL = f"{API_BASE}/post/publish/status/fetch/"
TOKEN_URL = f"{API_BASE}/oauth/token/"

DEFAULT_CHUNK_SIZE = 10 * 1024 * 1024


class TikTokError(Exception):
    pass


def _log_id(payload: dict) -> str:
    if isinstance(payload, dict):
        return str(payload.get("log_id") or payload.get("error", {}).get("log_id") or "")
    return ""


def _error_of(payload) -> str:
    if not isinstance(payload, dict):
        return "unexpected response"
    err = payload.get("error")
    if isinstance(err, dict):
        return f"{err.get('code')}: {err.get('message')}"
    if err:
        return f"{err}: {payload.get('error_description', '')}"
    if "data" not in payload:
        return f"unexpected response: {str(payload)[:200]}"
    return ""


def _auth_headers() -> dict:
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    if config.TT_ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {config.TT_ACCESS_TOKEN}"
    return headers


def _post_json(url: str, payload: dict, headers: dict | None = None, timeout: int = 30,
               expect_data: bool = True) -> dict:
    resp = requests.post(url, json=payload, headers=headers or _auth_headers(), timeout=timeout)
    try:
        data = resp.json()
    except ValueError:
        raise TikTokError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    if data.get("error") or (expect_data and "data" not in data):
        raise TikTokError(f"{_error_of(data)} (log_id={_log_id(data)}, http={resp.status_code})")
    return data


def _post_form(url: str, payload: dict, timeout: int = 30) -> dict:
    resp = requests.post(
        url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache"},
        timeout=timeout,
    )
    try:
        data = resp.json()
    except ValueError:
        raise TikTokError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    if data.get("error"):
        raise TikTokError(f"{_error_of(data)} (log_id={_log_id(data)}, http={resp.status_code})")
    return data


def refresh_access_token() -> bool:
    if not (config.TT_REFRESH_TOKEN and config.TT_CLIENT_KEY and config.TT_CLIENT_SECRET):
        logger.warning("TikTok: cannot refresh token, client credentials missing")
        return False
    payload = {
        "client_key": config.TT_CLIENT_KEY,
        "client_secret": config.TT_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": config.TT_REFRESH_TOKEN,
    }
    try:
        data = _post_form(TOKEN_URL, payload)
    except TikTokError as e:
        logger.error("TikTok: token refresh failed: %s", e)
        return False
    token = data.get("access_token")
    if not token:
        logger.error("TikTok: refresh response without access_token")
        return False
    config.TT_ACCESS_TOKEN = token
    if data.get("refresh_token"):
        config.TT_REFRESH_TOKEN = data["refresh_token"]
    if data.get("open_id"):
        config.TT_OPEN_ID = data["open_id"]
    logger.info(
        "TikTok: access token refreshed, valid %ss, refresh token %ss",
        data.get("expires_in"), data.get("refresh_expires_in"),
    )
    return True


_TOKEN_READY = False
_RETRY_AFTER = 0.0
_RETRY_DELAY = 300.0


def ensure_access_token() -> bool:
    """Return a usable access token, refreshing at most once per cooldown.

    A dead refresh token fails on every call, so without the cooldown each
    status poll hit TikTok again and filled the log with the same error.
    """
    global _TOKEN_READY, _RETRY_AFTER
    if _TOKEN_READY and config.TT_ACCESS_TOKEN:
        return True
    if config.TT_REFRESH_TOKEN and config.TT_CLIENT_KEY and config.TT_CLIENT_SECRET:
        if time.monotonic() < _RETRY_AFTER:
            return bool(config.TT_ACCESS_TOKEN)
        if refresh_access_token():
            _TOKEN_READY = True
            _RETRY_AFTER = 0.0
            return True
        _RETRY_AFTER = time.monotonic() + _RETRY_DELAY
        return bool(config.TT_ACCESS_TOKEN)
    return bool(config.TT_ACCESS_TOKEN)


def query_creator_info() -> dict:
    payload = {"fields": ["follower_count", "following_count", "likes_count", "video_count"]}
    return _post_json(CREATOR_INFO_URL, payload).get("data", {})


def available_privacy_levels() -> list[str]:
    if not config.TT_ACCESS_TOKEN:
        return [config.TT_PRIVACY_LEVEL]
    try:
        info = query_creator_info()
    except TikTokError as e:
        logger.warning("TikTok: creator info unavailable: %s", e)
        return [config.TT_PRIVACY_LEVEL]
    levels = info.get("privacy_level_options") or [config.TT_PRIVACY_LEVEL]
    if config.TT_PRIVACY_LEVEL not in levels:
        logger.warning(
            "TikTok: %s not allowed for this account, falling back to %s",
            config.TT_PRIVACY_LEVEL, levels[0],
        )
        return [levels[0]]
    return [config.TT_PRIVACY_LEVEL]


def build_title(text: str, max_chars: int = 0) -> str:
    limit = max_chars or config.TT_MAX_CHARS
    title = " ".join((text or "").split())
    if len(title) <= limit:
        return title
    return title[: limit - 1].rstrip() + "…"


def init_upload(video_size: int, title: str, privacy_level: str) -> dict:
    chunk_size = config.TT_CHUNK_SIZE or DEFAULT_CHUNK_SIZE
    payload = {
        "post_info": {
            "title": title,
            "privacy_level": privacy_level,
            "disable_duet": config.TT_DISABLE_DUET,
            "disable_comment": config.TT_DISABLE_COMMENT,
            "disable_stitch": config.TT_DISABLE_STITCH,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": chunk_size,
            "total_chunk_count": max(1, -(-video_size // chunk_size)),
        },
    }
    data = _post_json(VIDEO_INIT_URL, payload).get("data", {})
    if not data.get("publish_id") or not data.get("upload_url"):
        raise TikTokError(f"init returned no publish_id/upload_url: {str(data)[:200]}")
    return data


def upload_file(upload_url: str, video: io.BytesIO) -> None:
    size = len(video.getbuffer())
    chunk_size = config.TT_CHUNK_SIZE or DEFAULT_CHUNK_SIZE
    total_chunks = max(1, -(-size // chunk_size))
    video.seek(0)
    sent = 0

    for index in range(total_chunks):
        chunk = video.read(chunk_size)
        if not chunk:
            break
        start = sent
        sent += len(chunk)
        headers = {
            "Content-Range": f"bytes {start}-{sent - 1}/{size}",
            "Content-Type": "video/mp4",
        }
        resp = requests.put(upload_url, data=chunk, headers=headers, timeout=300)
        if resp.status_code not in (200, 201, 204):
            raise TikTokError(f"chunk {index + 1}/{total_chunks} failed: HTTP {resp.status_code} {resp.text[:200]}")
        logger.info("TikTok: uploaded %d/%d chunks", index + 1, total_chunks)


def fetch_status(publish_id: str) -> dict:
    return _post_json(STATUS_URL, {"publish_id": publish_id}).get("data", {})


def wait_for_status(publish_id: str, attempts: int = 0) -> dict:
    attempts = attempts or config.TT_STATUS_ATTEMPTS
    last = {}
    for _ in range(attempts):
        last = fetch_status(publish_id)
        state = last.get("status")
        if state and state != "PROCESSING_UPLOAD" and state != "PROCESSING_DOWNLOAD":
            return last
        time.sleep(config.TT_STATUS_INTERVAL)
    return last


def publish_video(video: io.BytesIO, text: str) -> str | None:
    if not config.TT_ENABLED:
        logger.info("TikTok: disabled by config")
        return None
    if not ensure_access_token():
        logger.warning("TikTok: no access token, skipping")
        return None
    if video is None:
        logger.warning("TikTok: no video to publish")
        return None

    privacy = available_privacy_levels()[0]
    title = build_title(text)
    logger.info("TikTok: publishing %d bytes, privacy=%s", len(video.getbuffer()), privacy)

    for attempt in (1, 2):
        try:
            data = init_upload(len(video.getbuffer()), title, privacy)
            upload_file(data["upload_url"], video)
            status = wait_for_status(data["publish_id"])
        except TikTokError as e:
            logger.error("TikTok: publish failed (attempt %d): %s", attempt, e)
            if attempt == 1 and refresh_access_token():
                continue
            return None
        except requests.RequestException as e:
            logger.error("TikTok: network error: %s", e)
            return None

        state = status.get("status", "UNKNOWN")
        if state == "PUBLISH_COMPLETE":
            logger.info("TikTok: published, publish_id=%s", data["publish_id"])
            return data["publish_id"]
        logger.error("TikTok: not published, status=%s %s", state, status.get("fail_reason") or "")
        return None

    return None


def post_article(text: str, title: str, description: str, image_buf: io.BytesIO) -> bool:
    from video_generator import image_to_video_vertical

    try:
        video = image_to_video_vertical(
            image_buf, title=title, source=config.BRAND_NAME, description=description, duration=0
        )
    except Exception as e:
        logger.error("TikTok: vertical render failed: %s", e)
        return False

    if video is None:
        logger.warning("TikTok: vertical video unavailable, skipping")
        return False

    if publish_video(video, text) is None:
        return False
    logger.info("TikTok: posted successfully")
    return True
