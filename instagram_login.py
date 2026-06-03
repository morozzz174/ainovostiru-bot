import sys
import os

os.environ.setdefault("DOTENV_PATH", ".env.facts")

import config
from instagram_publisher import _get_client

code = input("Введи код 2FA из WhatsApp: ").strip()
if code:
    config.IG_2FA_CODE = code
    cl = _get_client()
    if cl:
        print("Instagram: Вход выполнен! Сессия сохранена.")
    else:
        print("Instagram: Ошибка входа.")
else:
    print("Код не введён.")
