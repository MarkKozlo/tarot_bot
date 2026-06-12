from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from yookassa import Configuration, Payment
import uuid
from keyboards.keyboards import get_main_menu, get_buy_menu
from db.database import Database
from config import PACKAGES, PRICES, YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY
import os

if YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY:
    Configuration.account_id = YOOKASSA_SHOP_ID
    Configuration.secret_key = YOOKASSA_SECRET_KEY


class PaymentHandler:
    def __init__(self, db: Database):
        self.db = db
        self.pending_payments = {}
    
    async def show_buy_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        text = (
            "✦ ◈ ☽ ✧ ⟡\n\n"
            "💎 <b>Пополнить баланс</b>\n\n"
            "Выбери подходящий пакет:\n\n"
            "✦ Оплата картой (Visa, Mastercard, МИР)\n"
            "✦ Моментальное зачисление\n"
            "✦ Безопасная оплата через ЮKassa\n"
            "✦ Пакеты со скидкой до 53%\n\n"
            "✦ ◈ ☽ ✧ ⟡"
        )
        
        await query.message.edit_text(
            text,
            reply_markup=get_buy_menu(),
            parse_mode="HTML"
        )
    
    async def send_invoice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        package_key = query.data.replace("buy_", "")
        package = PACKAGES.get(package_key)
        price_rub = PRICES.get(package_key)
        
        if not package or not price_rub:
            await query.message.reply_text("❌ Пакет не найден")
            return
        
        if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
            await query.message.reply_text(
                "⚠️ <b>Платежи временно недоступны</b>\n\n"
                "Система оплаты настраивается. "
                "Попробуй позже или используй бесплатные расклады.",
                parse_mode="HTML"
            )
            return
        
        try:
            bot = await context.bot.get_me()
            return_url = f"https://t.me/{bot.username}"
            
            payment = Payment.create({
                "amount": {
                    "value": f"{price_rub}.00",
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": return_url
                },
                "capture": True,
                "description": f"Пакет: {package['name']} для Таро-бота",
                "metadata": {
                    "user_id": update.effective_user.id,
                    "package_key": package_key
                }
            }, uuid.uuid4())
            
            self.pending_payments[payment.id] = {
                "user_id": update.effective_user.id,
                "package_key": package_key,
                "spreads": package["spreads"]
            }
            
            confirmation_url = payment.confirmation.confirmation_url
            
            text = (
                f"💳 <b>Оплата пакета</b>\n\n"
                f"📦 Пакет: <b>{package['name']}</b>\n"
                f"💰 Сумма: <b>{price_rub} ₽</b>\n\n"
                f"Нажимая «Оплатить», ты соглашаешься с /terms\n\n"
                f"Нажми кнопку ниже для оплаты картой:"
            )
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Оплатить картой", url=confirmation_url)],
                [InlineKeyboardButton("❌ Отмена", callback_data="buy_menu")]
            ])
            
            await query.message.reply_text(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            context.job_queue.run_repeating(
                self.check_payment_status,
                interval=10,
                first=10,
                data={"payment_id": payment.id},
                name=f"check_{payment.id}"
            )
            
        except Exception as e:
            await query.message.reply_text(
                f"❌ Ошибка создания платежа: {str(e)}"
            )
    
    async def check_payment_status(self, context: ContextTypes.DEFAULT_TYPE):
        payment_id = context.job.data["payment_id"]
        
        try:
            payment = Payment.find_one(payment_id)
            
            if payment.status == "succeeded":
                payment_data = self.pending_payments.get(payment_id)
                
                if payment_data:
                    user_id = payment_data["user_id"]
                    package_key = payment_data["package_key"]
                    spreads = payment_data["spreads"]
                    
                    await self.db.add_balance(
                        user_id,
                        spreads,
                        package_key,
                        payment_id,
                        int(float(payment.amount.value))
                    )
                    
                    if package_key == "unlimited":
                        text = (
                            "🎉 <b>Оплата прошла успешно!</b>\n\n"
                            "У тебя теперь <b>♾️ Безлимитный доступ</b> на 30 дней!\n\n"
                            "Наслаждайся раскладами без ограничений ✨"
                        )
                    else:
                        balance = await self.db.get_balance(user_id)
                        text = (
                            f"🎉 <b>Оплата прошла успешно!</b>\n\n"
                            f"На твой баланс зачислено <b>{spreads} раскладов</b>.\n\n"
                            f"Текущий баланс: <b>{balance} раскладов</b>\n\n"
                            f"Благодарю за поддержку! ✦"
                        )
                    
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=text,
                        reply_markup=get_main_menu(1, 5),
                        parse_mode="HTML"
                    )
                    
                    del self.pending_payments[payment_id]
                    context.job.schedule_removal()
            
            elif payment.status in ["canceled", "expired"]:
                if payment_id in self.pending_payments:
                    del self.pending_payments[payment_id]
                context.job.schedule_removal()
        
        except Exception as e:
            print(f"Ошибка проверки платежа: {e}")
    
    async def precheckout_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        pass
    
    async def successful_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        pass