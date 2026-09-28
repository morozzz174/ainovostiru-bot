import logging
import os
import re
import secrets
import subprocess
import sys
import tempfile
import webbrowser
from urllib.parse import parse_qs, urlparse

import requests

import config

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
SCOPE = "video.publish,user.info.basic"
STATE_FILE = os.path.join(tempfile.gettempdir(), "tiktok_oauth_state.txt")


def read_clipboard() -> str:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
            capture_output=True, timeout=15,
        )
        if result.returncode == 0:
            return result.stdout.decode("utf-8", "ignore").strip()
    except Exception as e:
        logger.debug("clipboard read failed: %s", e)
    return ""


def update_env_file(values: dict, path: str = "") -> None:
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        raise SystemExit(f"Файл {path} не найден")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for key, value in values.items():
        pattern = re.compile(rf"(?m)^{re.escape(key)}=.*$")
        line = f"{key}={value}"
        if pattern.search(content):
            content = pattern.sub(line, content)
        else:
            content = content.rstrip("\n") + f"\n{line}\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Записано в {path}: {', '.join(values)}")


def build_authorize_url(client_key: str, redirect_uri: str, state: str) -> str:
    return (
        f"{AUTHORIZE_URL}?client_key={client_key}"
        f"&response_type=code"
        f"&scope={SCOPE}"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
    )


def extract_code(raw: str, expected_state: str) -> str:
    raw = raw.strip()
    if not raw:
        raise SystemExit("Пустой ответ: не удалось прочитать буфер обмена")

    if raw.startswith("http"):
        query = parse_qs(urlparse(raw).query)
    elif "=" in raw and "code" in raw.split("=")[0]:
        query = parse_qs(raw)
    else:
        return raw

    if "error" in query:
        raise SystemExit(
            "TikTok вернул ошибку: "
            f"{query.get('error_description', [''])[0] or query['error'][0]}"
        )

    returned_state = query.get("state", [""])[0]
    if expected_state and returned_state and returned_state != expected_state:
        raise SystemExit("state не совпадает, отмени авторизацию")

    if "code" not in query:
        raise SystemExit("В ссылке нет параметра code")
    return query["code"][0]


def exchange_code(code: str, client_key: str, client_secret: str, redirect_uri: str) -> dict:
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache"},
        timeout=30,
    )
    data = resp.json()
    if data.get("error"):
        raise SystemExit(f"Ошибка обмена кода: {data.get('error')} — {data.get('error_description')}")
    if not data.get("access_token"):
        raise SystemExit(f"В ответе нет access_token: {str(data)[:200]}")
    return data


def main() -> int:
    client_key = os.getenv("TT_CLIENT_KEY", config.TT_CLIENT_KEY)
    client_secret = os.getenv("TT_CLIENT_SECRET", config.TT_CLIENT_SECRET)
    redirect_uri = os.getenv("TT_REDIRECT_URI", config.TT_REDIRECT_URI)

    if not client_key or not client_secret:
        print("Нужны TT_CLIENT_KEY и TT_CLIENT_SECRET (впиши их в .env или передай через переменные окружения).")
        print("Они выдаются в консоли разработчика: https://developers.tiktok.com/apps/ -> твоё приложение -> App details")
        return 1

    state = secrets.token_urlsafe(24)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(state)

    url = build_authorize_url(client_key, redirect_uri, state)
    print("Открываю страницу авторизации...")
    print(url)
    print()
    print("Войди в TikTok и разреши доступ. После переадресации страница не откроется — это нормально.")
    webbrowser.open(url)

    print("Скопируй адрес из адресной строки (целиком) в буфер обмена и нажми Enter.")
    try:
        input()
    except EOFError:
        return 1

    raw = read_clipboard()
    if not raw:
        try:
            raw = input("Вставь ссылку сюда: ").strip()
        except EOFError:
            return 1

    code = extract_code(raw, state)
    print("Код получен, обмениваю на токены...")

    data = exchange_code(code, client_key, client_secret, redirect_uri)
    print(f"scope: {data.get('scope')}")
    print(f"access_token: {len(data.get('access_token', ''))} симв., живёт {data.get('expires_in')} c")
    print(f"refresh_token: живёт {data.get('refresh_expires_in')} c")

    update_env_file({
        "TT_ACCESS_TOKEN": data["access_token"],
        "TT_REFRESH_TOKEN": data.get("refresh_token", ""),
        "TT_OPEN_ID": data.get("open_id", ""),
        "TT_CLIENT_KEY": client_key,
        "TT_CLIENT_SECRET": client_secret,
        "TT_REDIRECT_URI": redirect_uri,
        "TT_ENABLED": "true",
    })

    print()
    print("Готово. Теперь те же значения положи в GitHub:")
    print("  Settings -> Secrets and variables -> Actions -> New repository secret")
    for name in ("TT_ACCESS_TOKEN", "TT_REFRESH_TOKEN", "TT_OPEN_ID", "TT_CLIENT_KEY", "TT_CLIENT_SECRET"):
        print(f"  - {name}")
    print("После этого добавь их в .github/workflows/newsbot.yml в env шага Run news collector.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
