"""MorozMax web control panel.

Web front-end for the TikTok Content Posting API integration. The browser is
the integration surface, so the demo video and the Website URL refer to the
same place where publishing actually happens.
"""

import asyncio
import base64
import hmac
import io
import json
import logging
import os
import secrets
import time
from collections import deque

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("web")

LOG_BUFFER: deque = deque(maxlen=2000)
_log_seq = 0


class _BufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        global _log_seq
        try:
            message = record.getMessage()
        except Exception:
            return
        _log_seq += 1
        LOG_BUFFER.append(
            {
                "seq": _log_seq,
                "ts": time.strftime("%H:%M:%S", time.localtime(record.created)),
                "level": record.levelname,
                "logger": record.name,
                "message": message,
            }
        )


_handler = _BufferHandler()
_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(_handler)
for _name in ("web", "tiktok_publisher", "video_generator", "voice", "music", "publisher", "collector", "translator", "image_finder"):
    logging.getLogger(_name).addHandler(_handler)

app = FastAPI(title="MorozMax", docs_url="/api/docs", redoc_url=None)

WEB_PASSWORD = os.getenv("WEB_PASSWORD", "")
COOKIE_NAME = "mm_session"
_sessions: set[str] = set()

_job_lock = asyncio.Lock()
_job_state: dict = {"running": False, "result": None, "started_at": None}


def require_auth(x_auth_token: str = Header(default="")) -> None:
    if not WEB_PASSWORD:
        return
    if x_auth_token and x_auth_token in _sessions:
        return
    raise HTTPException(status_code=401, detail="auth required")


async def _publish(article: dict) -> dict:
    """Run the full TikTok flow for one article, logging every step."""
    from collector import Article
    from publisher import prepare_post
    from storage import Storage
    from translator import translate_article
    import tiktok_publisher

    if not config.TT_ENABLED:
        logger.error("TikTok is disabled. Set TT_ENABLED=true in the environment.")
        return {"ok": False, "error": "TikTok disabled"}

    if not tiktok_publisher.ensure_access_token():
        logger.error("No valid access token. Run run_tiktok_auth.bat to authorize.")
        return {"ok": False, "error": "no access token"}

    levels = tiktok_publisher.available_privacy_levels()
    logger.info("Allowed privacy levels for this account: %s", ", ".join(levels))

    art = Article(
        title=article["title"],
        url=article["url"],
        description=article.get("description", ""),
        source=article.get("source", ""),
    )
    if art.lang == "en":
        logger.info("Translating article to Russian...")
        art.title, art.description = translate_article(art.title, art.description)
        art.lang = "ru"

    logger.info("Rendering branded image and 9:16 video...")
    text, image_buf, media_type = prepare_post(art)
    logger.info("Post text prepared (%d chars)", len(text))

    ok = tiktok_publisher.post_article(text, art.title, art.description, image_buf)
    if ok:
        Storage(config.DATABASE_PATH).mark_posted(art.url, art.title)
        logger.info("Article marked as posted")
        return {"ok": True, "url": art.url}

    logger.error("Publishing did not complete")
    return {"ok": False, "error": "publish failed", "url": art.url}


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    if WEB_PASSWORD:
        return HTMLResponse(LOGIN_PAGE)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "panel.html"), encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.post("/api/login")
async def login(payload: dict) -> dict:
    if not WEB_PASSWORD:
        return {"ok": True}
    if not hmac.compare_digest(str(payload.get("password", "")), WEB_PASSWORD):
        logger.warning("Rejected login attempt")
        raise HTTPException(status_code=401, detail="wrong password")
    token = secrets.token_urlsafe(24)
    _sessions.add(token)
    return {"ok": True, "token": token}


@app.get("/api/status", dependencies=[Depends(require_auth)])
async def status() -> dict:
    token_ok = False
    error = ""
    try:
        from tiktok_publisher import ensure_access_token
        token_ok = ensure_access_token()
    except Exception as e:
        error = str(e)

    return {
        "tiktok_enabled": config.TT_ENABLED,
        "has_token": token_ok,
        "privacy_level": config.TT_PRIVACY_LEVEL,
        "open_id": bool(config.TT_OPEN_ID),
        "theme": config.THEME,
        "brand": config.BRAND_NAME,
        "error": error,
        "job": _job_state,
    }


@app.get("/api/articles", dependencies=[Depends(require_auth)])
async def articles(limit: int = Query(12, ge=1, le=40)) -> dict:
    from collector import collect_news
    from storage import Storage

    try:
        collected = await asyncio.to_thread(collect_news)
    except Exception as e:
        logger.error("Collection failed: %s", e)
        return {"items": [], "error": str(e)}

    storage = Storage(config.DATABASE_PATH)
    items = []
    for art in collected:
        if storage.is_posted(art.url):
            continue
        items.append(
            {
                "title": art.title,
                "url": art.url,
                "description": art.description,
                "source": art.source,
                "lang": art.lang,
            }
        )
        if len(items) >= limit:
            break

    logger.info("Listed %d candidate articles", len(items))
    return {"items": items, "total_collected": len(collected)}


class PublishRequest(BaseModel):
    title: str
    url: str
    description: str = ""
    source: str = ""


@app.post("/api/publish", dependencies=[Depends(require_auth)])
async def publish(req: PublishRequest) -> dict:
    if _job_lock.locked():
        raise HTTPException(status_code=409, detail="a publish job is already running")

    _job_state.update({"running": True, "result": None, "started_at": time.time()})
    logger.info("Publish requested for: %s", req.title)

    async with _job_lock:
        try:
            result = await asyncio.to_thread(_publish, req.dict())
        except Exception as e:
            logger.exception("Publish crashed")
            result = {"ok": False, "error": str(e)}
        finally:
            _job_state.update({"running": False, "result": result})
    return result


@app.get("/api/logs", dependencies=[Depends(require_auth)])
async def logs(since: int = 0) -> dict:
    since = since or (LOG_BUFFER[0]["seq"] - 1 if LOG_BUFFER else 0)
    return {"items": [entry for entry in LOG_BUFFER if entry["seq"] > since], "seq": _log_seq}


LOGIN_PAGE = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>MorozMax — вход</title>
<style>
body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:#0f1117;color:#e8e8ee;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
.card{background:#181b24;padding:36px;border-radius:14px;width:320px;border:1px solid #262a36}
h1{font-size:20px;margin:0 0 4px}p{color:#8b8fa3;font-size:13px;margin:0 0 20px}
input,button{width:100%;padding:11px;border-radius:8px;font-size:14px;box-sizing:border-box}
input{background:#0f1117;border:1px solid #2c3140;color:#e8e8ee;margin-bottom:10px}
button{background:#5e6aff;border:0;color:#fff;cursor:pointer;font-weight:600}
.err{color:#ff6b6b;font-size:13px;min-height:18px;margin-bottom:8px}
</style></head><body>
<div class="card"><h1>MorozMax</h1><p>Панель управления публикацией</p>
<div class="err" id="e"></div>
<input id="p" type="password" placeholder="Пароль" autofocus>
<button onclick="go()">Войти</button></div>
<script>
async function go(){
  const r = await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:document.getElementById('p').value})});
  if(r.ok){const d=await r.json();localStorage.setItem('mm_token',d.token);location.href='/';}
  else{document.getElementById('e').textContent='Неверный пароль';}
}
document.getElementById('p').addEventListener('keydown',e=>{if(e.key==='Enter')go();});
</script></body></html>"""
