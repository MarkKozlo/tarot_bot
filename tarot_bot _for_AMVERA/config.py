import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")
DATABASE_PATH = os.getenv("DATABASE_PATH", "tarot_bot.db")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}" if WEBHOOK_HOST else None

# Цены в РУБЛЯХ (обновлённые конкурентные цены)
PRICES = {
    "single": 59,      # 1 расклад = 59 ₽
    "pack_5": 199,     # 5 раскладов = 199 ₽ (экономия 33%)
    "pack_10": 279,    # 10 раскладов = 279 ₽ (экономия 53%)
    "unlimited": 359,  # Безлимит 30 дней = 359 ₽ (экономия ~49%)
}

PACKAGES = {
    "single": {"spreads": 1, "name": "1 расклад"},
    "pack_5": {"spreads": 5, "name": "5 раскладов"},
    "pack_10": {"spreads": 10, "name": "10 раскладов"},
    "unlimited": {"spreads": -1, "name": "Безлимит на 30 дней"},
}

# Welcome-бонус для новых пользователей
WELCOME_BONUS = 1  # 1 бесплатный платный расклад при регистрации