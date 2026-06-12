from telegram import Update
from telegram.ext import ContextTypes
from keyboards.keyboards import get_back_to_main, CATEGORY_INFO
from utils.formatters import format_history_item
from db.database import Database


class HistoryHandler:
    def __init__(self, db: Database):
        self.db = db
    
    async def _format_history_text(self, user_id: int) -> str:
        history = await self.db.get_history(user_id, limit=10)
        
        if not history:
            return (
                "✦ ◈ ☽ ✧ ⟡\n\n"
                "📜 <b>История раскладов</b>\n\n"
                "У тебя пока нет сохранённых раскладов.\n"
                "Сделай первый расклад, и он появится здесь!\n\n"
                "✦ ◈ ☽ ✧ ⟡"
            )
        
        text = "✦ ◈ ☽ ✧ ⟡\n\n📜 <b>История твоих раскладов</b>\n\n✦ ◈ ☽ ✧ ⟡\n\n"
        
        for item in history:
            text += format_history_item(item) + "\n\n"
        
        text += "✦ ◈ ☽ ✧ ⟡"
        return text
    
    async def show_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        text = await self._format_history_text(update.effective_user.id)
        
        await query.message.edit_text(
            text,
            reply_markup=get_back_to_main(),
            parse_mode="HTML"
        )
    
    async def history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = await self._format_history_text(update.effective_user.id)
        
        await update.message.reply_text(
            text,
            reply_markup=get_back_to_main(),
            parse_mode="HTML"
        )