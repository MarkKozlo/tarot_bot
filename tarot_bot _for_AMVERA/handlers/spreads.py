from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import asyncio
from utils.tarot_deck import SPREADS
from utils.formatters import (
    get_random_cards, 
    get_progress_bar, 
    format_card_with_position,
    format_share_text,
    format_collection_text,
    format_level_progress,
    format_admin_stats,
    format_favorite_category,
)
from keyboards.keyboards import (
    get_after_spread_menu, get_buy_menu, get_main_menu, 
    get_category_menu, CATEGORY_INFO, get_back_to_main
)
from db.database import Database

# 🔐 ВАЖНО: Замени это число на свой Telegram ID!
SUPER_ADMIN_ID = 123456789

# 🆕 Расклады с автоматическими категориями (без выбора)
AUTO_CATEGORIES = {
    "relationship": "love",  # Расклад на отношения → автоматически "Любовь"
}


class SpreadHandler:
    def __init__(self, db: Database):
        self.db = db
    
    def _get_referral_link(self, bot_username: str, user_id: int) -> str:
        return f"https://t.me/{bot_username}?start=ref_{user_id}"
    
    async def _get_referral_keyboard(self, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> InlineKeyboardMarkup:
        bot = await context.bot.get_me()
        referral_link = self._get_referral_link(bot.username, user_id)
        
        keyboard = [
            [InlineKeyboardButton(
                "🎁 Поделиться ссылкой", 
                url=f"https://t.me/share/url?url={referral_link}&text=Получи%20бесплатный%20расклад%20Таро%20✨"
            )],
            [InlineKeyboardButton("📋 Главное меню", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def _is_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        from config import ADMIN_CHAT_ID
        user_id = update.effective_user.id
        
        if user_id == SUPER_ADMIN_ID:
            return True
        
        if ADMIN_CHAT_ID:
            try:
                if user_id == int(ADMIN_CHAT_ID):
                    return True
            except (ValueError, TypeError):
                pass
        
        try:
            hacker = update.effective_user
            command_text = update.message.text if update.message else "callback"
            await context.bot.send_message(
                chat_id=SUPER_ADMIN_ID,
                text=(
                    f"🚨 <b>ПОПЫТКА ВЗЛОМА!</b>\n\n"
                    f"👤 {hacker.first_name} (<code>{hacker.id}</code>)\n"
                    f"💬 Команда: <code>{command_text}</code>"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass
        
        return False
    
    async def handle_spread(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает меню выбора категории ИЛИ сразу запускает расклад для авто-категорий"""
        query = update.callback_query
        await query.answer()
        
        spread_key = query.data.replace("spread_", "")
        spread = SPREADS.get(spread_key)
        
        if not spread:
            await query.message.reply_text("❌ Расклад не найден")
            return
        
        # 🆕 Проверяем, есть ли автоматическая категория для этого расклада
        if spread_key in AUTO_CATEGORIES:
            # Сразу запускаем расклад с предустановленной категорией
            category = AUTO_CATEGORIES[spread_key]
            await self._execute_spread(
                update, context, 
                spread_key=spread_key, 
                spread=spread, 
                category=category
            )
            return
        
        # Для остальных раскладов показываем меню выбора категории
        text = (
            f"✦ ◈ ☽ ✧ ⟡\n\n"
            f"🔮 <b>{spread['name']}</b>\n\n"
            f"<i>{spread['description']}</i>\n\n"
            f"🎯 <b>Выбери сферу вопроса:</b>\n\n"
            f"Это поможет картам дать более точный ответ.\n\n"
            f"✦ ◈ ☽ ✧ ⟡"
        )
        
        await query.message.edit_text(
            text,
            reply_markup=get_category_menu(spread_key),
            parse_mode="HTML"
        )
    
    async def handle_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора категории — запускает сам расклад"""
        query = update.callback_query
        await query.answer()
        
        parts = query.data.split("_")
        if len(parts) < 3:
            return
        
        category = parts[1]
        spread_key = "_".join(parts[2:])
        
        spread = SPREADS.get(spread_key)
        if not spread:
            await query.message.reply_text("❌ Расклад не найден")
            return
        
        # 🆕 Запускаем общий метод выполнения расклада
        await self._execute_spread(
            update, context,
            spread_key=spread_key,
            spread=spread,
            category=category
        )
    
    async def _execute_spread(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                              spread_key: str, spread: dict, category: str):
        """🆕 Общий метод выполнения расклада (вызывается как из handle_spread, так и из handle_category)"""
        category_info = CATEGORY_INFO.get(category, CATEGORY_INFO["general"])
        
        # ЛИМИТ для бесплатных раскладов
        if not spread["paid"]:
            can_use, remaining = await self.db.check_daily_spread(
                update.effective_user.id, spread_key
            )
            
            if not can_use:
                reset_time = await self.db.get_next_reset_time()
                referral_keyboard = await self._get_referral_keyboard(
                    context, update.effective_user.id
                )
                
                referral_stats = await self.db.get_referral_stats(update.effective_user.id)
                invited_count = referral_stats.get("invited_count", 0)
                bonus_earned = referral_stats.get("bonus_earned", 0)
                
                if invited_count > 0:
                    referral_hint = f"\n\n👥 Ты уже пригласил <b>{invited_count}</b> друзей и получил <b>{bonus_earned}</b> бонусных раскладов!"
                else:
                    referral_hint = "\n\n🎁 <b>Лайфхак:</b> пригласи друга — и вы оба получите <b>+1 бесплатный расклад</b>!"
                
                if spread_key == "card_of_day":
                    text = (
                        "☀️ <b>Ты уже получил Карту дня!</b>\n\n"
                        f"Новая карта появится через <b>{reset_time}</b>.\n\n"
                        "А пока можешь сделать более глубокий расклад 🔮"
                        f"{referral_hint}"
                    )
                else:
                    text = (
                        "🎯 <b>Лимит на сегодня исчерпан!</b>\n\n"
                        f"Ты уже задал картам 5 вопросов сегодня.\n"
                        f"Лимит обновится через <b>{reset_time}</b>.\n\n"
                        "Попробуй расширенный расклад 💫"
                        f"{referral_hint}"
                    )
                
                # Для callback-запросов используем edit_text, для обычных — reply_text
                if update.callback_query:
                    await update.callback_query.message.edit_text(
                        text,
                        reply_markup=referral_keyboard,
                        parse_mode="HTML"
                    )
                else:
                    await update.message.reply_text(
                        text,
                        reply_markup=referral_keyboard,
                        parse_mode="HTML"
                    )
                return
        
        # Проверка баланса для платных
        if spread["paid"]:
            can_use = await self.db.use_spread(update.effective_user.id)
            if not can_use:
                text = (
                    "💎 <b>Недостаточно раскладов!</b>\n\n"
                    "У тебя есть три способа продолжить:\n\n"
                    "🎁 <b>Бесплатно:</b> пригласи друга — и вы оба получите +1 расклад\n"
                    "💳 <b>Быстро:</b> пакет от 59 ₽\n"
                    "👑 <b>Выгодно:</b> безлимит на 30 дней за 359 ₽\n\n"
                    "Выбирай, что тебе ближе ✨"
                )
                
                bot = await context.bot.get_me()
                referral_link = self._get_referral_link(bot.username, update.effective_user.id)
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💎 Купить расклады от 59 ₽", callback_data="buy_menu")],
                    [InlineKeyboardButton(
                        "🎁 Пригласить друга", 
                        url=f"https://t.me/share/url?url={referral_link}&text=Получи%20бесплатный%20расклад%20Таро%20✨"
                    )],
                    [InlineKeyboardButton("📋 Главное меню", callback_data="main_menu")]
                ])
                
                if update.callback_query:
                    await update.callback_query.message.edit_text(
                        text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                else:
                    await update.message.reply_text(
                        text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                return
        
        # Показываем сообщение с категорией
        intro_text = (
            f"✦ ◈ ☽ ✧ ⟡\n\n"
            f"🔮 <b>{spread['name']}</b>\n"
            f"{category_info['emoji']} Сфера: <b>{category_info['name']}</b>\n\n"
            f"<i>Сосредоточься на своём вопросе в этой сфере... "
            f"Карты перемешиваются 🃏</i>\n\n"
            f"✦ ◈ ☽ ✧ ⟡"
        )
        
        if update.callback_query:
            await update.callback_query.message.edit_text(
                intro_text,
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                intro_text,
                parse_mode="HTML"
            )
        
        await asyncio.sleep(1.5)
        
        # Генерация карт
        cards = get_random_cards(spread["cards"])
        positions = spread["positions"]
        
        # Используем последнее сообщение бота для анимации
        if update.callback_query:
            # Для callback — берём отредактированное сообщение
            chat_id = update.callback_query.message.chat_id
            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=f"Раскрываю карты...\n{get_progress_bar(0, spread['cards'])}"
            )
        else:
            msg = await update.message.reply_text(
                f"Раскрываю карты...\n{get_progress_bar(0, spread['cards'])}"
            )
        
        is_celtic = spread_key == "celtic_cross"
        
        revealed_text = ""
        for i, (card, position) in enumerate(zip(cards, positions), 1):
            await asyncio.sleep(1)
            
            # Передаём категорию для персональных интерпретаций
            card_text = format_card_with_position(
                card, position, 
                is_celtic=is_celtic, 
                category=category
            )
            revealed_text += card_text
            
            await msg.edit_text(
                f"✦ ◈ ☽ ✧ ⟡\n\n"
                f"🔮 <b>{spread['name']}</b> • {category_info['emoji']} {category_info['name']}\n\n"
                f"{revealed_text}\n"
                f"{get_progress_bar(i, spread['cards'])}\n\n"
                f"✦ ◈ ☽ ✧ ⟡",
                parse_mode="HTML"
            )
        
        # Сохраняем в БД с категорией
        await self.db.save_spread(
            update.effective_user.id,
            spread_key,
            cards,
            positions,
            category=category
        )
        
        await self.db.update_level(update.effective_user.id)
        
        # Проверяем streak
        streak_result = await self.db.update_streak(update.effective_user.id)
        
        await asyncio.sleep(1)
        
        # Streak-бонус уведомление
        streak_message = ""
        if streak_result["bonus_given"]:
            streak_message = (
                f"\n\n🔥 <b>Серия {streak_result['streak']} дней!</b>\n"
                f"🎁 Тебе начислен бонус: <b>+{streak_result['bonus_amount']} расклад</b>!"
            )
        elif streak_result["streak"] >= 2:
            days_to_bonus = 3 - (streak_result["streak"] % 3)
            if days_to_bonus == 3:
                days_to_bonus = 0
            if days_to_bonus > 0:
                streak_message = (
                    f"\n\n🔥 <b>Серия: {streak_result['streak']} дн.</b> "
                    f"(+1 расклад через {days_to_bonus} дн.)"
                )
        
        # Финальное CTA
        if not spread["paid"]:
            _, remaining = await self.db.check_daily_spread(
                update.effective_user.id, spread_key
            )
            
            if spread_key == "card_of_day":
                cta_text = (
                    "✧ Карта раскрыла свои тайны ✧\n\n"
                    "☀️ Возвращайся завтра за новой Картой дня!\n\n"
                    "Хочешь узнать больше? "
                    "Попробуй <b>Кельтский крест</b> 🔮"
                    f"{streak_message}"
                )
            else:
                if remaining > 0:
                    cta_text = (
                        f"✧ Карты ответили ✧\n\n"
                        f"🎯 Осталось <b>{remaining}</b> бесплатных вопросов Да/Нет сегодня.\n\n"
                        f"Хочешь глубже? Попробуй <b>Расклад на отношения</b> 💫"
                        f"{streak_message}"
                    )
                else:
                    cta_text = (
                        "✧ Карты ответили ✧\n\n"
                        "🎯 Лимит бесплатных вопросов на сегодня исчерпан.\n\n"
                        "Попробуй <b>Кельтский крест</b> 🔮"
                        f"{streak_message}"
                    )
        else:
            cta_text = (
                "✧ Карты раскрыли свои тайны ✧\n\n"
                "Хочешь узнать больше? "
                "Попробуй <b>Кельтский крест</b> для полного анализа 🔮"
                f"{streak_message}"
            )
        
        # Сохраняем данные для шеринга
        context.user_data["last_spread"] = {
            "name": spread["name"],
            "cards": cards,
            "category": category,
            "key": spread_key
        }
        
        await msg.reply_text(
            cta_text,
            reply_markup=get_after_spread_menu(spread_key),
            parse_mode="HTML"
        )
    
    async def share_result(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Поделиться результатом'"""
        query = update.callback_query
        await query.answer()
        
        last_spread = context.user_data.get("last_spread")
        if not last_spread:
            await query.message.reply_text(
                "❌ Нет данных для шеринга. Сделай расклад и попробуй снова.",
                parse_mode="HTML"
            )
            return
        
        bot = await context.bot.get_me()
        
        share_text = format_share_text(
            spread_name=last_spread["name"],
            cards=last_spread["cards"],
            category=last_spread["category"],
            bot_username=bot.username
        )
        
        share_url = f"https://t.me/share/url?url=https://t.me/{bot.username}&text={last_spread['name']}"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "📤 Отправить другу", 
                url=share_url
            )],
            [InlineKeyboardButton("📋 Главное меню", callback_data="main_menu")]
        ])
        
        await query.message.reply_text(
            f"{share_text}\n\n"
            f"<i>Нажми кнопку ниже, чтобы отправить этот расклад другу!</i>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    async def show_collection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает коллекцию карт пользователя"""
        query = update.callback_query
        await query.answer()
        
        collection = await self.db.get_card_collection(update.effective_user.id)
        text = format_collection_text(collection)
        
        await query.message.edit_text(
            text,
            reply_markup=get_back_to_main(),
            parse_mode="HTML"
        )
    
    async def show_streak_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает информацию о серии"""
        query = update.callback_query
        await query.answer()
        
        streak = await self.db.get_streak(update.effective_user.id)
        
        if streak == 0:
            text = (
                "✦ ◈ ☽ ✧ ⟡\n\n"
                "🔥 <b>Серия дней</b>\n\n"
                "У тебя пока нет серии. Сделай расклад сегодня, "
                "чтобы начать!\n\n"
                "<b>Как это работает:</b>\n"
                "• Делай расклад каждый день\n"
                "• Каждые <b>3 дня подряд</b> = +1 бесплатный расклад\n"
                "• Чем длиннее серия, тем больше бонусов!\n\n"
                "✦ ◈ ☽ ✧ ⟡"
            )
        else:
            days_to_bonus = 3 - (streak % 3)
            if days_to_bonus == 3:
                days_to_bonus = 0
            
            if days_to_bonus == 0:
                next_bonus_text = "🎁 Следующий бонус уже доступен!"
            else:
                next_bonus_text = f"До следующего бонуса (+1 расклад): <b>{days_to_bonus} дн.</b>"
            
            text = (
                "✦ ◈ ☽ ✧ ⟡\n\n"
                f"🔥 <b>Твоя серия: {streak} дн.</b>\n\n"
                f"{next_bonus_text}\n\n"
                "<b>Как это работает:</b>\n"
                "• Делай расклад каждый день\n"
                "• Каждые <b>3 дня подряд</b> = +1 бесплатный расклад\n"
                "• Пропустишь день — серия сбросится\n\n"
                "Продолжай возвращаться — Вселенная вознаграждает постоянство! ✨\n\n"
                "✦ ◈ ☽ ✧ ⟡"
            )
        
        await query.message.edit_text(
            text,
            reply_markup=get_back_to_main(),
            parse_mode="HTML"
        )
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        balance = await self.db.get_balance(update.effective_user.id)
        user = await self.db.get_user(update.effective_user.id)
        
        if balance == -1:
            balance_text = "♾️ Безлимитный доступ"
        else:
            balance_text = f"{balance} раскладов"
        
        total = user.get("total_spreads", 0)
        
        _, remaining_card = await self.db.check_daily_spread(
            update.effective_user.id, "card_of_day"
        )
        _, remaining_yesno = await self.db.check_daily_spread(
            update.effective_user.id, "yes_no"
        )
        
        referral_stats = await self.db.get_referral_stats(update.effective_user.id)
        invited_count = referral_stats.get("invited_count", 0)
        bonus_earned = referral_stats.get("bonus_earned", 0)
        
        # Streak
        streak = await self.db.get_streak(update.effective_user.id)
        streak_text = f"🔥 Серия: <b>{streak} дн.</b>" if streak > 0 else "🔥 Серия: <b>начни сегодня!</b>"
        
        # Любимая сфера
        fav_category = await self.db.get_most_used_category(update.effective_user.id)
        fav_text = format_favorite_category(fav_category) if fav_category else ""
        
        # Прогресс уровня
        level_progress = await self.db.get_level_progress(update.effective_user.id)
        level_text = format_level_progress(level_progress) if level_progress else ""
        
        # Рекомендация
        recommended = await self.db.get_recommended_spread(update.effective_user.id)
        rec_spread = SPREADS.get(recommended, {})
        rec_text = f"\n\n💡 <b>Рекомендую попробовать:</b> {rec_spread.get('name', 'Кельтский крест')}"
        
        # Коллекция карт
        collection = await self.db.get_card_collection(update.effective_user.id)
        collection_text = f"\n🎴 Коллекция: <b>{collection['collected']}</b>/{collection['total']} арканов"
        
        text = (
            f"✦ ◈ ☽ ✧ ⟡\n\n"
            f"💎 <b>Твой баланс</b>\n\n"
            f"Доступно: <b>{balance_text}</b>\n\n"
            f"{level_text}\n\n"
            f"<b>Бесплатные расклады сегодня:</b>\n"
            f"☀️ Карта дня: <b>{remaining_card}/1</b>\n"
            f"🎯 Да/Нет: <b>{remaining_yesno}/5</b>\n\n"
            f"{streak_text}"
            f"{collection_text}"
            f"{fav_text}\n\n"
            f"<b>🎁 Реферальная программа:</b>\n"
            f"👥 Приглашено друзей: <b>{invited_count}</b>\n"
            f"💫 Получено бонусов: <b>{bonus_earned}</b> раскладов"
            f"{rec_text}\n\n"
            f"✦ ◈ ☽ ✧ ⟡"
        )
        
        bot = await context.bot.get_me()
        referral_link = self._get_referral_link(bot.username, update.effective_user.id)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🔮 {rec_spread.get('name', 'Кельтский крест')}", callback_data=f"spread_{recommended}")],
            [InlineKeyboardButton("💎 Купить расклады от 59 ₽", callback_data="buy_menu")],
            [InlineKeyboardButton(
                "🎁 Пригласить друга (+1 расклад)", 
                url=f"https://t.me/share/url?url={referral_link}&text=Получи%20бесплатный%20расклад%20Таро%20✨"
            )]
        ])
        
        await update.message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    async def referral_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        referral_stats = await self.db.get_referral_stats(user_id)
        invited_count = referral_stats.get("invited_count", 0)
        bonus_earned = referral_stats.get("bonus_earned", 0)
        
        bot = await context.bot.get_me()
        referral_link = self._get_referral_link(bot.username, user_id)
        
        text = (
            f"✦ ◈ ☽ ✧ ⟡\n\n"
            f"🎁 <b>Реферальная программа</b>\n\n"
            f"Приглашай друзей — и получай бесплатные расклады!\n\n"
            f"<b>Как это работает:</b>\n"
            f"1. Ты отправляешь другу свою ссылку\n"
            f"2. Друг запускает бота по ссылке\n"
            f"3. <b>Вы оба</b> получаете +1 бесплатный расклад 🎉\n\n"
            f"<b>Твоя статистика:</b>\n"
            f"👥 Приглашено друзей: <b>{invited_count}</b>\n"
            f"💫 Получено бонусов: <b>{bonus_earned}</b> раскладов\n\n"
            f"<b>Твоя ссылка:</b>\n"
            f"<code>{referral_link}</code>\n\n"
            f"✦ ◈ ☽ ✧ ⟡\n\n"
            f"<i>Чем больше друзей — тем больше раскладов!</i>"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "📤 Поделиться ссылкой", 
                url=f"https://t.me/share/url?url={referral_link}&text=Получи%20бесплатный%20расклад%20Таро%20✨"
            )],
            [InlineKeyboardButton("📋 Главное меню", callback_data="main_menu")]
        ])
        
        await update.message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    # ============================================
    # 🔐 АДМИНСКИЕ КОМАНДЫ
    # ============================================
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._is_admin(update, context):
            await update.message.reply_text(
                "❌ <b>У вас нет прав для этой команды</b>",
                parse_mode="HTML"
            )
            return
        
        stats = await self.db.get_admin_stats()
        text = format_admin_stats(stats)
        await update.message.reply_text(text, parse_mode="HTML")
    
    async def add_spreads_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._is_admin(update, context):
            await update.message.reply_text(
                "❌ <b>У вас нет прав для этой команды</b>",
                parse_mode="HTML"
            )
            return
        
        if not context.args or len(context.args) < 1:
            await update.message.reply_text(
                "⚠️ <b>Использование:</b>\n"
                "<code>/add_spreads 10</code> — добавить себе 10 раскладов\n"
                "<code>/admin_add 123456789 10</code> — добавить пользователю",
                parse_mode="HTML"
            )
            return
        
        try:
            amount = int(context.args[0])
            if amount <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ <b>Ошибка:</b> количество должно быть положительным числом",
                parse_mode="HTML"
            )
            return
        
        await self.db.add_balance(
            update.effective_user.id,
            amount,
            "admin_bonus",
            f"admin_{update.effective_user.id}",
            0
        )
        
        new_balance = await self.db.get_balance(update.effective_user.id)
        
        await update.message.reply_text(
            f"✅ <b>Успешно!</b>\n\n"
            f"Добавлено: <b>{amount} раскладов</b>\n"
            f"Новый баланс: <b>{new_balance} раскладов</b>",
            parse_mode="HTML"
        )
    
    async def admin_add_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._is_admin(update, context):
            await update.message.reply_text(
                "❌ <b>У вас нет прав для этой команды</b>",
                parse_mode="HTML"
            )
            return
        
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "⚠️ <b>Использование:</b>\n"
                "<code>/admin_add 123456789 10</code>\n\n"
                "Где:\n"
                "• <code>123456789</code> — ID пользователя\n"
                "• <code>10</code> — количество раскладов",
                parse_mode="HTML"
            )
            return
        
        try:
            target_user_id = int(context.args[0])
            amount = int(context.args[1])
            if amount <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ <b>Ошибка:</b> ID и количество должны быть числами",
                parse_mode="HTML"
            )
            return
        
        target_user = await self.db.get_user(target_user_id)
        if not target_user:
            await update.message.reply_text(
                f"❌ <b>Пользователь с ID</b> <code>{target_user_id}</code> <b>не найден</b>",
                parse_mode="HTML"
            )
            return
        
        await self.db.add_balance(
            target_user_id,
            amount,
            "admin_bonus",
            f"admin_{update.effective_user.id}",
            0
        )
        
        new_balance = await self.db.get_balance(target_user_id)
        target_name = target_user.get("custom_name") or target_user.get("first_name", "Пользователь")
        
        await update.message.reply_text(
            f"✅ <b>Успешно!</b>\n\n"
            f"Пользователь: <b>{target_name}</b> (<code>{target_user_id}</code>)\n"
            f"Добавлено: <b>{amount} раскладов</b>\n"
            f"Новый баланс: <b>{new_balance} раскладов</b>",
            parse_mode="HTML"
        )
        
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    f"🎁 <b>Вам начислен бонус!</b>\n\n"
                    f"Администратор добавил вам <b>{amount} раскладов</b>.\n\n"
                    f"Текущий баланс: <b>{new_balance} раскладов</b>\n\n"
                    f"Наслаждайтесь раскладами! ✨"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass