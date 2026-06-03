import io
import logging
import os
import pickle
import tempfile
import time
from pathlib import Path

from instagrapi import Client
from instagrapi.exceptions import (
    ClientError,
    LoginRequired,
    ReloginAttemptExceeded,
    ChallengeRequired,
    FeedbackRequired,
    PleaseWaitFewMinutes,
    TwoFactorRequired,
)

import config

logger = logging.getLogger(__name__)

SESSION_FILE = Path("instagram_session.pkl")


def _resolve_2fa(cl: Client, username: str) -> None:
    if not cl.two_factor_code_fn:
        logger.warning("2FA required but no code handler set. Check IG_2FA_CODE or IG_2FA_CALLBACK")
        raise TwoFactorRequired("No 2FA handler configured")


def _resolve_challenge(cl: Client, username: str) -> None:
    try:
        challenge = cl.challenge_resolve(cl.last_json)
        logger.info("Instagram: challenge resolved: %s", challenge)
    except Exception as e:
        logger.error("Instagram: challenge resolve failed: %s", e)
        raise


def _get_client() -> Client | None:
    if not config.IG_USERNAME or not config.IG_PASSWORD:
        logger.warning("Instagram credentials not configured")
        return None

    cl = Client()

    cl.delay_range = config.IG_DELAY_RANGE
    cl.request_timeout = config.IG_REQUEST_TIMEOUT

    if config.IG_PROXY:
        cl.set_proxy(config.IG_PROXY)
        logger.info("Instagram: using proxy %s", config.IG_PROXY)

    if config.IG_USER_AGENT:
        cl.set_user_agent(config.IG_USER_AGENT)
        cl.set_device(config.IG_DEVICE)
        cl.set_locale(config.IG_LOCALE)

    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE, "rb") as f:
                cached_settings = pickle.load(f)
            cl.set_settings(cached_settings)

            try:
                cl.login(config.IG_USERNAME, config.IG_PASSWORD)
                logger.info("Instagram: logged in via saved session")
                return cl
            except LoginRequired:
                logger.warning("Instagram: session expired, re-login required")
                SESSION_FILE.unlink(missing_ok=True)
            except ChallengeRequired:
                logger.info("Instagram: challenge required, attempting to resolve")
                _resolve_challenge(cl, config.IG_USERNAME)
                with open(SESSION_FILE, "wb") as f:
                    pickle.dump(cl.get_settings(), f)
                return cl
        except Exception as e:
            logger.warning("Instagram: session load failed: %s", e)
            SESSION_FILE.unlink(missing_ok=True)

    cl.two_factor_code_fn = config.IG_2FA_CALLBACK or _noop_code_fn

    for attempt in range(config.IG_LOGIN_MAX_RETRIES):
        try:
            cl.login(config.IG_USERNAME, config.IG_PASSWORD)

            with open(SESSION_FILE, "wb") as f:
                pickle.dump(cl.get_settings(), f)
            logger.info("Instagram: logged in and session saved")
            return cl

        except TwoFactorRequired:
            logger.info("Instagram: 2FA required, calling verification code handler")
            _resolve_2fa(cl, config.IG_USERNAME)
            with open(SESSION_FILE, "wb") as f:
                pickle.dump(cl.get_settings(), f)
            return cl

        except ChallengeRequired:
            logger.info("Instagram: challenge required (attempt %d/%d)", attempt + 1, config.IG_LOGIN_MAX_RETRIES)
            try:
                _resolve_challenge(cl, config.IG_USERNAME)
                with open(SESSION_FILE, "wb") as f:
                    pickle.dump(cl.get_settings(), f)
                return cl
            except Exception:
                if attempt == config.IG_LOGIN_MAX_RETRIES - 1:
                    raise

        except FeedbackRequired as e:
            logger.error("Instagram: feedback required (action blocked): %s", e)
            wait = config.IG_FEEDBACK_WAIT
            logger.info("Instagram: waiting %d seconds before retry...", wait)
            time.sleep(wait)

        except PleaseWaitFewMinutes as e:
            logger.warning("Instagram: rate limited: %s", e)
            time.sleep(120)

        except ReloginAttemptExceeded:
            logger.error("Instagram: too many login attempts, waiting longer")
            time.sleep(300)

        except ClientError as e:
            logger.error("Instagram: client error (attempt %d/%d): %s", attempt + 1, config.IG_LOGIN_MAX_RETRIES, e)
            if attempt < config.IG_LOGIN_MAX_RETRIES - 1:
                time.sleep(config.IG_RETRY_DELAY)

    logger.error("Instagram: login failed after %d attempts", config.IG_LOGIN_MAX_RETRIES)
    return None


def _prompt_2fa_code() -> str:
    if config.IG_2FA_CODE:
        return config.IG_2FA_CODE
    code = input("Instagram 2FA код (пришёл в WhatsApp?): ").strip()
    if code:
        return code
    return ""


_noop_code_fn = _prompt_2fa_code


def _temp_save(image_buf: io.BytesIO) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    tmp.write(image_buf.read())
    tmp.close()
    return tmp.name


def post_article(text: str, image_buf: io.BytesIO) -> bool:
    cl = _get_client()
    if not cl:
        return False

    image_buf.seek(0)

    for attempt in range(config.IG_POST_MAX_RETRIES):
        tmp_path = None
        try:
            caption = _format_caption(text)
            image_buf.seek(0)
            tmp_path = _temp_save(image_buf)
            cl.photo_upload(tmp_path, caption)
            logger.info("Instagram: post published")
            return True

        except LoginRequired:
            logger.warning("Instagram: session expired during post, re-logging in")
            SESSION_FILE.unlink(missing_ok=True)
            cl = _get_client()
            if not cl:
                return False

        except ChallengeRequired:
            logger.info("Instagram: challenge during post, attempting to resolve")
            try:
                _resolve_challenge(cl, config.IG_USERNAME)
            except Exception:
                return False

        except FeedbackRequired as e:
            logger.error("Instagram: action blocked: %s", e)
            if attempt < config.IG_POST_MAX_RETRIES - 1:
                time.sleep(60)

        except PleaseWaitFewMinutes as e:
            logger.warning("Instagram: rate limited: %s", e)
            time.sleep(120)

        except Exception as e:
            logger.error("Instagram: post failed (attempt %d/%d): %s", attempt + 1, config.IG_POST_MAX_RETRIES, e)
            if attempt < config.IG_POST_MAX_RETRIES - 1:
                time.sleep(config.IG_RETRY_DELAY)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    logger.error("Instagram: post failed after %d attempts", config.IG_POST_MAX_RETRIES)
    return False


def _format_caption(text: str) -> str:
    text = text.replace("*", "").replace("_", "")
    lines = text.split("\n")
    clean = []
    hashtags = []
    for line in lines:
        line = line.strip()
        if line.startswith("📅 Источник:"):
            clean.append(line.replace("📅 Источник: [", "📅 Источник: ").replace("](", " (").rstrip(")"))
        elif line.startswith("#"):
            hashtags.append(line)
        elif line:
            clean.append(line)

    result = "\n\n".join(clean)
    if hashtags:
        result += "\n\n" + " ".join(hashtags)

    if len(result) > 2200:
        result = result[:2197] + "..."

    return result
