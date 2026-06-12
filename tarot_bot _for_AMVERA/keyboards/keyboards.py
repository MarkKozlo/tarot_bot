from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu(remaining_card: int = 1, remaining_yesno: int = 5, streak: int = 0) -> InlineKeyboardMarkup:
    card_text = "☀️ Карта дня (бесплатно)" if remaining_card > 0 else "☀️ Карта дня (завтра)"
    yesno_text = f"🎯 Да/Нет ({remaining_yesno}/5 бесплатно)" if remaining_yesno > 0 else "🎯 Да/Нет (завтра)"
    
    # 🆕 Streak-индикатор
    streak_button = []
    if streak >= 3:
        streak_button = [[InlineKeyboardButton(f"🔥 Серия: {streak} дн.", callback_data="streak_info")]]
    
    keyboard = [
        [InlineKeyboardButton(card_text, callback_data="spread_card_of_day")],
        [InlineKeyboardButton(yesno_text, callback_data="spread_yes_no")],
        [InlineKeyboardButton("⏳ Прошлое-Настоящее-Будущее", callback_data="spread_past_present_future")],
        [InlineKeyboardButton("💫 Расклад на отношения", callback_data="spread_relationship")],
        [InlineKeyboardButton("🔮 Кельтский крест", callback_data="spread_celtic_cross")],
    ] + streak_button + [
        [InlineKeyboardButton("💎 Купить расклады", callback_data="buy_menu")],
        [InlineKeyboardButton("🎴 Моя коллекция карт", callback_data="collection")],
        [InlineKeyboardButton("📜 История раскладов", callback_data="history")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_onboarding_goal() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("❤️ Любовь и отношения", callback_data="goal_love")],
        [InlineKeyboardButton("💼 Работа и карьера", callback_data="goal_work")],
        [InlineKeyboardButton("🌱 Саморазвитие", callback_data="goal_growth")],
        [InlineKeyboardButton("🔮 Общий расклад", callback_data="goal_general")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_category_menu(spread_key: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("❤️ Любовь и отношения", callback_data=f"category_love_{spread_key}")],
        [InlineKeyboardButton("💼 Работа и карьера", callback_data=f"category_work_{spread_key}")],
        [InlineKeyboardButton("🌱 Саморазвитие", callback_data=f"category_growth_{spread_key}")],
        [InlineKeyboardButton("🔮 Общий вопрос", callback_data=f"category_general_{spread_key}")],
        [InlineKeyboardButton("◀️ Назад в меню", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


CATEGORY_INFO = {
    "love": {"emoji": "❤️", "name": "Любовь"},
    "work": {"emoji": "💼", "name": "Работа"},
    "growth": {"emoji": "🌱", "name": "Саморазвитие"},
    "general": {"emoji": "🔮", "name": "Общий вопрос"},
}


def get_buy_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("💳 1 расклад — 59 ₽", callback_data="buy_single")],
        [InlineKeyboardButton("💳 5 раскладов — 199 ₽ 🔥", callback_data="buy_pack_5")],
        [InlineKeyboardButton("💳 10 раскладов — 279 ₽ 💎", callback_data="buy_pack_10")],
        [InlineKeyboardButton("👑 Безлимит на 30 дней — 359 ₽", callback_data="buy_unlimited")],
        [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_after_spread_menu(spread_key: str = "celtic_cross") -> InlineKeyboardMarkup:
    """🆕 Добавлена кнопка 'Поделиться'"""
    keyboard = [
        [InlineKeyboardButton("📤 Поделиться результатом", callback_data=f"share_{spread_key}")],
        [InlineKeyboardButton("🔮 Хочешь больше? Кельтский крест", callback_data="spread_celtic_cross")],
        [InlineKeyboardButton("💎 Купить расклады", callback_data="buy_menu")],
        [InlineKeyboardButton("📋 Главное меню", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_to_main() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📋 Главное меню", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_daily_card_optin() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("✅ Да, хочу карту дня!", callback_data="optin_daily_yes")],
        [InlineKeyboardButton("❌ Нет, спасибо", callback_data="optin_daily_no")],
    ]
    return InlineKeyboardMarkup(keyboard)