import logging
import sys
import warnings
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    PreCheckoutQueryHandler,
    filters,
    ContextTypes,
    JobQueue,
)
from telegram.error import TelegramError
from telegram.warnings import PTBUserWarning

warnings.filterwarnings("ignore", category=PTBUserWarning)

# 🆕 Подавляем шумные логи httpx
logging.getLogger("httpx").setLevel(logging.WARNING)

from config import BOT_TOKEN, ADMIN_CHAT_ID
from db.database import Database
from handlers.start import StartHandler, ASK_NAME
from handlers.spreads import SpreadHandler
from handlers.payments import PaymentHandler
from handlers.history import HistoryHandler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


class TarotBot:
    def __init__(self):
        self.db = Database("tarot_bot.db")
        self.start_handler = StartHandler(self.db)
        self.spread_handler = SpreadHandler(self.db)
        self.payment_handler = PaymentHandler(self.db)
        self.history_handler = HistoryHandler(self.db)
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Exception while handling update {update}: {context.error}")
        
        if ADMIN_CHAT_ID:
            try:
                error_msg = f"⚠️ <b>Ошибка в боте!</b>\n\n<code>{context.error}</code>"
                await context.bot.send_message(
                    chat_id=int(ADMIN_CHAT_ID),
                    text=error_msg,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to send error alert: {e}")
    
    async def post_init(self, application: Application):
        await self.db.init_db()
        logger.info("Database initialized")
    
    def build_application(self) -> Application:
        builder = Application.builder().token(BOT_TOKEN)
        builder.post_init(self.post_init)
        
        job_queue = JobQueue()
        builder.job_queue(job_queue)
        
        application = builder.build()
        
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.start_handler.start)],
            states={
                ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.start_handler.ask_name)],
            },
            fallbacks=[CommandHandler("start", self.start_handler.start)],
        )
        
        application.add_handler(conv_handler)
        application.add_handler(CallbackQueryHandler(
            self.start_handler.main_menu_callback, pattern="^main_menu$"
        ))
        application.add_handler(CallbackQueryHandler(
            self.start_handler.daily_optin, pattern="^optin_daily_"
        ))
        
        # Расклады
        application.add_handler(CallbackQueryHandler(
            self.spread_handler.handle_spread, pattern="^spread_"
        ))
        application.add_handler(CallbackQueryHandler(
            self.spread_handler.handle_category, pattern="^category_"
        ))
        
        # 🆕 Новые callback handlers
        application.add_handler(CallbackQueryHandler(
            self.spread_handler.share_result, pattern="^share_"
        ))
        application.add_handler(CallbackQueryHandler(
            self.spread_handler.show_collection, pattern="^collection$"
        ))
        application.add_handler(CallbackQueryHandler(
            self.spread_handler.show_streak_info, pattern="^streak_info$"
        ))
        
        # Платежи
        application.add_handler(CallbackQueryHandler(
            self.payment_handler.show_buy_menu, pattern="^buy_menu$"
        ))
        application.add_handler(CallbackQueryHandler(
            self.payment_handler.send_invoice, pattern="^buy_"
        ))
        application.add_handler(PreCheckoutQueryHandler(self.payment_handler.precheckout_callback))
        application.add_handler(MessageHandler(
            filters.SUCCESSFUL_PAYMENT, self.payment_handler.successful_payment
        ))
        
        # История
        application.add_handler(CallbackQueryHandler(
            self.history_handler.show_history, pattern="^history$"
        ))
        
        # Публичные команды
        application.add_handler(CommandHandler("balance", self.spread_handler.balance_command))
        application.add_handler(CommandHandler("referral", self.spread_handler.referral_command))
        application.add_handler(CommandHandler("history", self.history_handler.history_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("terms", self.terms_command))
        application.add_handler(CommandHandler("privacy", self.terms_command))
        
        # 🔐 Админские команды
        application.add_handler(CommandHandler("stats", self.spread_handler.stats_command))
        application.add_handler(CommandHandler("add_spreads", self.spread_handler.add_spreads_command))
        application.add_handler(CommandHandler("admin_add", self.spread_handler.admin_add_command))
        
        application.add_error_handler(self.error_handler)
        return application
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "✦ ◈ ☽ ✧ ⟡\n\n"
            "🔮 <b>Помощь</b>\n\n"
            "<b>Команды:</b>\n"
            "/start — Главное меню\n"
            "/balance — Твой баланс и прогресс\n"
            "/history — История раскладов\n"
            "/referral — Пригласить друга (+1 расклад)\n"
            "/terms — Условия использования\n"
            "/privacy — Политика конфиденциальности\n\n"
            "<b>Типы раскладов:</b>\n"
            "☀️ Карта дня — бесплатно (1/день)\n"
            "🎯 Да/Нет — бесплатно (5/день)\n"
            "⏳ Прошлое-Настоящее-Будущее — 1 расклад\n"
            "💫 Расклад на отношения — 1 расклад\n"
            "🔮 Кельтский крест — 1 расклад\n\n"
            "<b>💎 Пакеты со скидкой:</b>\n"
            "• 1 расклад — 59 ₽\n"
            "• 5 раскладов — 199 ₽ (экономия 33%)\n"
            "• 10 раскладов — 279 ₽ (экономия 53%)\n"
            "• Безлимит 30 дней — 359 ₽\n\n"
            "<b>🔥 Механики удержания:</b>\n"
            "• Серия дней — бонус каждые 3 дня\n"
            "• Коллекция карт — собирай все 22 Аркана\n"
            "• Уровни — от Новичка до Верховного Жреца\n\n"
            "<b>Проблемы с оплатой?</b>\n"
            "Напиши в поддержку: @your_username\n\n"
            "✦ ◈ ☽ ✧ ⟡"
        )
        await update.message.reply_text(text, parse_mode="HTML")
    
    async def terms_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "📜 <b>Условия использования и Оферта</b>\n\n"
            "✦ ◈ ☽ ✧ ⟡\n\n"
            "<b>1. Общие положения</b>\n"
            "Данный бот предоставляет интерактивные расклады Таро "
            "исключительно в развлекательных и познавательных целях.\n\n"
            
            "<b>2. Отказ от ответственности</b>\n"
            "• Бот НЕ является медицинской, психологической "
            "или юридической консультацией\n"
            "• Решения на основе раскладов принимаешь только ты\n"
            "• Администрация не несёт ответственности за последствия\n\n"
            
            "<b>3. Платежи и возвраты</b>\n"
            "• Оплата производится через защищённый шлюз ЮKassa\n"
            "• Возврат возможен в течение 14 дней, если услуга не оказана\n"
            "• Для возврата напиши в поддержку\n\n"
            
            "<b>4. Персональные данные</b>\n"
            "Мы храним только минимальные данные: "
            "ID Telegram и историю раскладов. "
            "Никаких телефонов, email и карт.\n\n"
            
            "<b>5. Контакты</b>\n"
            "📧 Поддержка: @your_username\n"
            "🏢 ИП Иванов И.И.\n"
            "📋 ИНН: 123456789012\n\n"
            
            "✦ ◈ ☽ ✧ ⟡\n\n"
            "<i>Продолжая использование бота, ты соглашаешься с условиями.</i>"
        )
        await update.message.reply_text(text, parse_mode="HTML")
    
    def run(self):
        application = self.build_application()
        logger.info("Starting bot...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    bot = TarotBot()
    bot.run()