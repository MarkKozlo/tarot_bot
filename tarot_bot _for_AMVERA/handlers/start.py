from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
from keyboards.keyboards import get_main_menu, get_daily_card_optin
from db.database import Database

ASK_NAME = 0


class StartHandler:
    def __init__(self, db: Database):
        self.db = db
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user = update.effective_user
        
        # Обработка реферальной ссылки
        referrer_id = None
        if context.args and len(context.args) > 0:
            arg = context.args[0]
            if arg.startswith("ref_"):
                try:
                    referrer_id = int(arg.replace("ref_", ""))
                except ValueError:
                    pass
        
        user_data = await self.db.get_or_create_user(
            user.id, user.username, user.first_name
        )
        
        # Реферальный бонус
        if referrer_id and user_data.get("is_new"):
            success = await self.db.process_referral(referrer_id, user.id)
            if success:
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=(
                            f"🎉 <b>Отличные новости!</b>\n\n"
                            f"Твой друг <b>{user.first_name}</b> запустил бота по твоей ссылке!\n\n"
                            f"💫 Тебе зачислен <b>+1 бесплатный расклад</b>.\n"
                            f"Другу тоже начислен бонус 🎁\n\n"
                            f"Продолжай приглашать — и получай больше раскладов!"
                        ),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
        
        if user_data.get("is_new"):
            welcome_bonus = user_data.get("welcome_bonus", 0)
            
            welcome_text = (
                f"✨ Добро пожаловать, {user.first_name}!\n\n"
                "Я — твой проводник в мир Таро. Здесь ты найдёшь ответы, "
                "поддержку и подсказки Вселенной.\n\n"
                f"🎁 <b>Тебе начислен welcome-бонус: {welcome_bonus} платный расклад</b> "
                "в подарок!\n\n"
                "Прежде чем мы начнём — как мне к тебе обращаться? "
                "(можешь пропустить, просто напиши '-')"
            )
            
            await update.message.reply_text(
                welcome_text,
                reply_markup=None,
                parse_mode="HTML"
            )
            return ASK_NAME
        else:
            await self.show_main_menu(update, context, user_data.get("user"))
            return ConversationHandler.END
    
    async def ask_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        custom_name = update.message.text.strip()
        if custom_name == "-":
            custom_name = update.effective_user.first_name
        
        # Сохраняем имя (goal больше не храним — выбирается перед каждым раскладом)
        await self.db.update_user_profile(
            update.effective_user.id, custom_name, ""
        )
        
        await update.message.reply_text(
            f"Приятно познакомиться, {custom_name}! ☽\n\n"
            "А ещё я могу присылать тебе Карту дня каждое утро? "
            "Это бесплатная мини-подсказка на весь день ✧",
            reply_markup=get_daily_card_optin(),
            parse_mode="HTML"
        )
        return ConversationHandler.END
    
    async def daily_optin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        streak = await self.db.get_streak(update.effective_user.id)
        
        if query.data == "optin_daily_yes":
            context.user_data["daily_optin"] = True
            await query.message.reply_text(
                "Прекрасно! ☀️ Буду присылать тебе Карту дня каждое утро.\n\n"
                "Теперь ты готов к своему первому раскладу!",
                reply_markup=get_main_menu(1, 5, streak)
            )
        else:
            context.user_data["daily_optin"] = False
            await query.message.reply_text(
                "Хорошо! Ты всегда можешь включить это позже.\n\n"
                "Готов к своему первому раскладу?",
                reply_markup=get_main_menu(1, 5, streak)
            )
    
    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user: dict):
        custom_name = user.get("custom_name") or update.effective_user.first_name
        
        _, remaining_card = await self.db.check_daily_spread(update.effective_user.id, "card_of_day")
        _, remaining_yesno = await self.db.check_daily_spread(update.effective_user.id, "yes_no")
        
        streak = await self.db.get_streak(update.effective_user.id)
        
        balance = await self.db.get_balance(update.effective_user.id)
        balance_text = "♾️ Безлимит" if balance == -1 else f"{balance} раскладов"
        
        # Рекомендация расклада
        recommended = await self.db.get_recommended_spread(update.effective_user.id)
        from utils.tarot_deck import SPREADS
        rec_spread_name = SPREADS.get(recommended, {}).get("name", "")
        
        # 🆕 Любимая сфера
        fav_category = await self.db.get_most_used_category(update.effective_user.id)
        if fav_category:
            from keyboards.keyboards import CATEGORY_INFO
            cat_info = CATEGORY_INFO.get(fav_category, CATEGORY_INFO["general"])
            fav_text = f"\n{cat_info['emoji']} Твоя сфера: <b>{cat_info['name']}</b>"
        else:
            fav_text = ""
        
        streak_text = f"\n🔥 Серия: <b>{streak} дн.</b>" if streak >= 2 else ""
        rec_text = f"\n\n💡 <i>Советую попробовать: <b>{rec_spread_name}</b></i>" if rec_spread_name else ""
        
        text = (
            f"✦ ◈ ☽ ✧ ⟡\n\n"
            f"Привет, {custom_name}! ✨{streak_text}{fav_text}\n\n"
            f"💎 Твой баланс: <b>{balance_text}</b>"
            f"{rec_text}\n\n"
            f"Выбери расклад, который откликается тебе сейчас.\n"
            f"Перед каждым раскладом ты сможешь выбрать сферу вопроса.\n\n"
            f"✦ ◈ ☽ ✧ ⟡"
        )
        
        await update.message.reply_text(
            text,
            reply_markup=get_main_menu(remaining_card, remaining_yesno, streak),
            parse_mode="HTML"
        )
    
    async def main_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user = await self.db.get_user(update.effective_user.id)
        custom_name = user.get("custom_name") or update.effective_user.first_name
        
        _, remaining_card = await self.db.check_daily_spread(update.effective_user.id, "card_of_day")
        _, remaining_yesno = await self.db.check_daily_spread(update.effective_user.id, "yes_no")
        
        streak = await self.db.get_streak(update.effective_user.id)
        
        balance = await self.db.get_balance(update.effective_user.id)
        balance_text = "♾️ Безлимит" if balance == -1 else f"{balance} раскладов"
        
        recommended = await self.db.get_recommended_spread(update.effective_user.id)
        from utils.tarot_deck import SPREADS
        rec_spread_name = SPREADS.get(recommended, {}).get("name", "")
        
        # 🆕 Любимая сфера
        fav_category = await self.db.get_most_used_category(update.effective_user.id)
        if fav_category:
            from keyboards.keyboards import CATEGORY_INFO
            cat_info = CATEGORY_INFO.get(fav_category, CATEGORY_INFO["general"])
            fav_text = f"\n{cat_info['emoji']} Твоя сфера: <b>{cat_info['name']}</b>"
        else:
            fav_text = ""
        
        streak_text = f"\n🔥 Серия: <b>{streak} дн.</b>" if streak >= 2 else ""
        rec_text = f"\n\n💡 <i>Советую попробовать: <b>{rec_spread_name}</b></i>" if rec_spread_name else ""
        
        text = (
            f"✦ ◈ ☽ ✧ ⟡\n\n"
            f"С возвращением, {custom_name}!{streak_text}{fav_text}\n\n"
            f"💎 Твой баланс: <b>{balance_text}</b>"
            f"{rec_text}\n\n"
            f"Выбери расклад:\n\n"
            f"✦ ◈ ☽ ✧ ⟡"
        )
        
        await query.message.edit_text(
            text,
            reply_markup=get_main_menu(remaining_card, remaining_yesno, streak),
            parse_mode="HTML"
        )