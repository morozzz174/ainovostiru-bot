import json
import os
import re
import sys

import requests

BASE = "https://api.github.com"
CREDENTIALS = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.actions")

WORKFLOWS = {
    "ai": "newsbot.yml",
    "facts": "factumbot.yml",
    "beauty": "beautybot.yml",
    "pages": "pages.yml",
}


def load_credentials(path: str = CREDENTIALS) -> dict:
    values: dict[str, str] = {}
    if not os.path.exists(path):
        return values
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "ainovostiru-dispatch",
    }


def dispatch(workflow: str, ref: str = "main", path: str = CREDENTIALS) -> tuple[bool, str]:
    creds = load_credentials(path)
    token = creds.get("GITHUB_PAT", "")
    owner = creds.get("GITHUB_OWNER", "")
    repo = creds.get("GITHUB_REPO", "")
    if not (token and owner and repo):
        return False, f"нет учётных данных в {path} (нужны GITHUB_PAT, GITHUB_OWNER, GITHUB_REPO)"

    url = f"{BASE}/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
    resp = requests.post(url, json={"ref": ref}, headers=_headers(token), timeout=30)
    if resp.status_code in (204, 200):
        return True, f"запущен {workflow} на {ref}"
    detail = resp.text[:300]
    try:
        detail = json.loads(resp.text).get("message", detail)
    except ValueError:
        pass
    return False, f"HTTP {resp.status_code}: {detail}"


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print("Использование: python github_dispatch.py <ai|facts|beauty|pages|all> [ref]")
        print("Токен берётся из .env.actions рядом со скриптом.")
        return 0

    targets = list(WORKFLOWS) if argv[1] == "all" else [argv[1]]
    ref = argv[2] if len(argv) > 2 else "main"

    failed = 0
    for target in targets:
        workflow = WORKFLOWS.get(target)
        if not workflow:
            print(f"неизвестная цель: {target}")
            failed += 1
            continue
        ok, message = dispatch(workflow, ref)
        print(f"{'OK  ' if ok else 'FAIL'} {target:7s} {message}")
        if not ok:
            failed += 1

    creds = load_credentials()
    owner, repo = creds.get("GITHUB_OWNER", ""), creds.get("GITHUB_REPO", "")
    if owner and repo:
        print(f"\nПрогоны: https://github.com/{owner}/{repo}/actions")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
