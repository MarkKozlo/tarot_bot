import random
from typing import List, Dict
from utils.tarot_deck import MAJOR_ARCANA, SPREADS
from keyboards.keyboards import CATEGORY_INFO


def get_random_cards(count: int) -> List[Dict]:
    cards_ids = random.sample(list(MAJOR_ARCANA.keys()), count)
    result = []
    for card_id in cards_ids:
        is_reversed = random.choice([True, False])
        result.append({
            "id": card_id,
            "reversed": is_reversed,
            **MAJOR_ARCANA[card_id]
        })
    return result


def format_card_with_position(card: Dict, position: str, is_celtic: bool = False, category: str = "general") -> str:
    """Форматирование карты с учётом категории.
    
    Для Кельтского креста:
    - Строка 2 (курсив): ОБЩЕЕ значение карты (всегда из upright/reversed)
    - Строка 3 (обычный): УНИКАЛЬНЫЙ персональный совет из categories[category]
    """
    direction = " (Перевёрнутая)" if card["reversed"] else ""
    key = "reversed" if card["reversed"] else "upright"
    
    # 🎯 БАЗОВОЕ значение карты (теория, всегда одинаковое для этой карты)
    base_interpretation = card[key]
    
    if is_celtic:
        # 🎯 ПЕРСОНАЛЬНОЕ значение для Кельтского креста (уникальный совет)
        if "categories" in card and category in card["categories"]:
            personal_meaning = card["categories"][category].get(key, base_interpretation)
        elif "celtic" in card:
            personal_meaning = card["celtic"].get(key, base_interpretation)
        else:
            personal_meaning = base_interpretation
        
        # Делаем первую букву базового значения маленькой (для курсива)
        interpretation_lower = base_interpretation[0].lower() + base_interpretation[1:] if base_interpretation else ""
        
        text = (
            f"\n<b>{position}: {card['name']}{direction}</b>\n"
            f"{card['emoji']} <i>{interpretation_lower}</i>\n"
            f"{personal_meaning}\n"
            f"\n◈ ───────────── ◈\n"
        )
    else:
        # Для обычных раскладов используем персонализацию по категории
        if "categories" in card and category in card["categories"]:
            interpretation = card["categories"][category].get(key, base_interpretation)
        else:
            interpretation = base_interpretation
        
        text = (
            f"\n{card['emoji']} <b>{card['name']}{direction}</b>\n\n"
            f"<i>{interpretation}</i>\n"
        )
    return text


def format_full_spread(spread_name: str, cards: List[Dict], positions: List[str], is_celtic: bool = False, category: str = "general") -> str:
    header = f"✦ ◈ ☽ ✧ ⟡\n\n🔮 <b>{spread_name}</b>\n\n✦ ◈ ☽ ✧ ⟡\n"
    
    body = ""
    for card, position in zip(cards, positions):
        body += format_card_with_position(card, position, is_celtic=is_celtic, category=category)
    
    footer = "\n✧ Да будет так ✧"
    return header + body + footer


def get_progress_bar(step: int, total: int) -> str:
    filled = "🔮" * step
    empty = "⚪" * (total - step)
    return f"{filled}{empty}"


def format_history_item(item: Dict) -> str:
    date = item["date"][:10]
    spread_key = item["type"]
    spread_name = SPREADS.get(spread_key, {}).get("name", spread_key)
    category = item.get("category", "general")
    category_info = CATEGORY_INFO.get(category, CATEGORY_INFO["general"])
    
    cards_str = ", ".join([
        f"{card['name']}{'↻' if card['reversed'] else ''}"
        for card in item["cards"]
    ])
    
    return (
        f"📅 {date}\n"
        f"🔮 {spread_name} • {category_info['emoji']} {category_info['name']}\n"
        f"🃏 {cards_str}"
    )


def get_level_info(total_spreads: int) -> str:
    if total_spreads >= 50:
        return "👑 Верховный Жрец"
    elif total_spreads >= 20:
        return "🧙 Маг"
    elif total_spreads >= 5:
        return "🔍 Искатель"
    else:
        return "🌱 Новичок"


def format_level_progress(progress_data: dict) -> str:
    if not progress_data:
        return ""
    
    current = progress_data["current"]
    progress = progress_data["progress"]
    needed = progress_data["needed"]
    percentage = progress_data["percentage"]
    
    filled_blocks = int(percentage / 10)
    bar = "▰" * filled_blocks + "▱" * (10 - filled_blocks)
    
    text = f"{current['emoji']} <b>{current['name']}</b> ({progress_data['total_spreads']} раскладов)\n"
    text += f"<code>{bar}</code> {percentage}%\n"
    
    next_lvl = progress_data.get("next")
    if next_lvl:
        remaining = next_lvl["required"] - progress_data["total_spreads"]
        text += f"До {next_lvl['emoji']} <b>{next_lvl['name']}</b>: <b>{remaining}</b> раскладов"
    else:
        text += "✨ <i>Максимальный уровень достигнут!</i>"
    
    return text


def format_share_text(spread_name: str, cards: List[Dict], category: str, bot_username: str) -> str:
    category_info = CATEGORY_INFO.get(category, CATEGORY_INFO["general"])
    
    cards_summary = "\n".join([
        f"{card['emoji']} {card['name']}{' ↻' if card['reversed'] else ''}"
        for card in cards[:5]
    ])
    
    if len(cards) > 5:
        cards_summary += f"\n<i>...и ещё {len(cards) - 5} карт</i>"
    
    return (
        f"✨ <b>Мой расклад Таро</b> ✨\n\n"
        f"🔮 {spread_name}\n"
        f"{category_info['emoji']} {category_info['name']}\n\n"
        f"{cards_summary}\n\n"
        f"✦ ◈ ☽ ✧ ⟡\n\n"
        f"<i>Хочешь узнать, что говорят карты тебе?</i>\n"
        f"👉 @{bot_username}"
    )


def format_collection_text(collection: dict) -> str:
    collected = collection["collected"]
    total = collection["total"]
    percentage = collection["percentage"]
    
    filled = int(percentage / 10)
    bar = "▰" * filled + "▱" * (10 - filled)
    
    if percentage == 100:
        status = "🌟 Коллекция собрана полностью!"
    elif percentage >= 75:
        status = "✨ Почти вся коллекция!"
    elif percentage >= 50:
        status = "🎯 Больше половины!"
    elif percentage >= 25:
        status = "🌱 Хорошее начало!"
    else:
        status = "🔍 Начало пути"
    
    return (
        f"✦ ◈ ☽ ✧ ⟡\n\n"
        f"🎴 <b>Твоя коллекция Арканов</b>\n\n"
        f"Собрано: <b>{collected}</b> из <b>{total}</b>\n"
        f"<code>{bar}</code> {percentage}%\n\n"
        f"{status}\n\n"
        f"<i>Делай больше раскладов, чтобы открыть все 22 Старших Аркана!</i>\n\n"
        f"✦ ◈ ☽ ✧ ⟡"
    )


def format_admin_stats(stats: dict) -> str:
    return (
        f"📊 <b>Статистика бота</b>\n\n"
        f"<b>👥 Пользователи:</b>\n"
        f"• Всего: <b>{stats['total_users']}</b>\n"
        f"• Новых сегодня: <b>{stats['new_today']}</b>\n"
        f"• Новых за неделю: <b>{stats['new_week']}</b>\n"
        f"• Активных за неделю: <b>{stats['active_week']}</b>\n\n"
        f"<b>🔮 Расклады:</b>\n"
        f"• Сегодня: <b>{stats['spreads_today']}</b>\n\n"
        f"<b>💰 Монетизация:</b>\n"
        f"• Платящих сегодня: <b>{stats['payers_today']}</b>\n"
        f"• Выручка сегодня: <b>{stats['revenue_today']} ₽</b>\n"
        f"• Всего платящих: <b>{stats['total_payers']}</b>\n"
        f"• Общая выручка: <b>{stats['total_revenue']} ₽</b>\n\n"
        f"<b>🏆 Уровни пользователей:</b>\n"
        f"• 🌱 Новичок: {stats['levels'].get('Новичок', 0)}\n"
        f"• 🔍 Искатель: {stats['levels'].get('Искатель', 0)}\n"
        f"• 🧙 Маг: {stats['levels'].get('Маг', 0)}\n"
        f"• 👑 Верховный Жрец: {stats['levels'].get('Верховный Жрец', 0)}"
    )


def format_favorite_category(category: str) -> str:
    """Форматирует блок 'Любимая сфера' для статистики"""
    if not category:
        return ""
    
    cat_info = CATEGORY_INFO.get(category, CATEGORY_INFO["general"])
    
    tips = {
        "love": "Попробуй <b>Расклад на отношения</b> для глубокого анализа 💫",
        "work": "Кельтский крест раскроет карьерные перспективы 🔮",
        "growth": "Прошлое-Настоящее-Будущее покажет путь развития ⏳",
        "general": "Карта дня даст подсказку на сегодня ☀️"
    }
    
    return (
        f"\n\n{cat_info['emoji']} <b>Твоя любимая сфера:</b> {cat_info['name']}\n"
        f"<i>{tips.get(category, '')}</i>"
    )