import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    custom_name TEXT,
                    goal TEXT,
                    balance INTEGER DEFAULT 0,
                    is_unlimited BOOLEAN DEFAULT FALSE,
                    unlimited_until TEXT,
                    total_spreads INTEGER DEFAULT 0,
                    level TEXT DEFAULT 'Новичок',
                    referred_by INTEGER,
                    welcome_bonus_used BOOLEAN DEFAULT FALSE,
                    streak INTEGER DEFAULT 0,
                    last_spread_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Миграции
            for migration in [
                "ALTER TABLE users ADD COLUMN referred_by INTEGER",
                "ALTER TABLE users ADD COLUMN welcome_bonus_used BOOLEAN DEFAULT FALSE",
                "ALTER TABLE users ADD COLUMN streak INTEGER DEFAULT 0",
                "ALTER TABLE users ADD COLUMN last_spread_date TEXT",
            ]:
                try:
                    await db.execute(migration)
                except Exception:
                    pass
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS spreads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    spread_type TEXT,
                    cards TEXT,
                    positions TEXT,
                    category TEXT DEFAULT 'general',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            ''')
            
            try:
                await db.execute("ALTER TABLE spreads ADD COLUMN category TEXT DEFAULT 'general'")
            except Exception:
                pass
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    package_type TEXT,
                    spreads_added INTEGER,
                    amount_stars INTEGER,
                    telegram_charge_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.commit()
    
    async def get_or_create_user(self, user_id: int, username: str, first_name: str) -> Dict:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            )
            user = await cursor.fetchone()
            
            if not user:
                from config import WELCOME_BONUS
                await db.execute(
                    """INSERT INTO users (user_id, username, first_name, balance) 
                       VALUES (?, ?, ?, ?)""",
                    (user_id, username, first_name, WELCOME_BONUS)
                )
                await db.commit()
                return {"is_new": True, "welcome_bonus": WELCOME_BONUS}
            
            return {"is_new": False, "user": dict(user)}
    
    async def update_user_profile(self, user_id: int, custom_name: str, goal: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET custom_name = ?, goal = ? WHERE user_id = ?",
                (custom_name, goal, user_id)
            )
            await db.commit()
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            )
            user = await cursor.fetchone()
            return dict(user) if user else None
    
    async def get_balance(self, user_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT balance, is_unlimited, unlimited_until FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return 0
            
            balance, is_unlimited, unlimited_until = row
            
            if is_unlimited and unlimited_until:
                until_date = datetime.fromisoformat(unlimited_until)
                if datetime.now() < until_date:
                    return -1
                else:
                    await db.execute(
                        "UPDATE users SET is_unlimited = FALSE WHERE user_id = ?",
                        (user_id,)
                    )
                    await db.commit()
            
            return balance
    
    async def use_spread(self, user_id: int) -> bool:
        balance = await self.get_balance(user_id)
        
        if balance == -1:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE users SET total_spreads = total_spreads + 1 WHERE user_id = ?",
                    (user_id,)
                )
                await db.commit()
            await self.update_streak(user_id)
            return True
        
        if balance > 0:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE users SET balance = balance - 1, total_spreads = total_spreads + 1 WHERE user_id = ?",
                    (user_id,)
                )
                await db.commit()
            await self.update_streak(user_id)
            return True
        
        return False
    
    async def add_balance(self, user_id: int, amount: int, package_type: str, charge_id: str, stars: int):
        async with aiosqlite.connect(self.db_path) as db:
            if package_type == "unlimited":
                until = (datetime.now() + timedelta(days=30)).isoformat()
                await db.execute(
                    """UPDATE users SET is_unlimited = TRUE, unlimited_until = ? 
                       WHERE user_id = ?""",
                    (until, user_id)
                )
            else:
                await db.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                    (amount, user_id)
                )
            
            await db.execute(
                """INSERT INTO payments (user_id, package_type, spreads_added, amount_stars, telegram_charge_id) 
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, package_type, amount, stars, charge_id)
            )
            await db.commit()
    
    async def save_spread(self, user_id: int, spread_type: str, cards: List, positions: List, category: str = "general"):
        import json
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO spreads (user_id, spread_type, cards, positions, category) 
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, spread_type, 
                 json.dumps(cards, ensure_ascii=False), 
                 json.dumps(positions, ensure_ascii=False),
                 category)
            )
            await db.commit()
    
    async def get_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        import json
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT spread_type, cards, positions, created_at, category 
                   FROM spreads WHERE user_id = ? 
                   ORDER BY created_at DESC LIMIT ?""",
                (user_id, limit)
            )
            rows = await cursor.fetchall()
            return [
                {
                    "type": row[0],
                    "cards": json.loads(row[1]),
                    "positions": json.loads(row[2]),
                    "date": row[3],
                    "category": row[4] if len(row) > 4 else "general"
                }
                for row in rows
            ]
    
    async def get_users_for_daily_card(self) -> List[int]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT user_id FROM users")
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
    
    async def update_level(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT total_spreads FROM users WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return
            
            spreads = row[0]
            if spreads >= 50:
                level = "Верховный Жрец"
            elif spreads >= 20:
                level = "Маг"
            elif spreads >= 5:
                level = "Искатель"
            else:
                level = "Новичок"
            
            await db.execute(
                "UPDATE users SET level = ? WHERE user_id = ?", (level, user_id)
            )
            await db.commit()
    
    async def check_daily_spread(self, user_id: int, spread_type: str) -> tuple:
        LIMITS = {
            "card_of_day": 1,
            "yes_no": 5,
        }
        limit = LIMITS.get(spread_type, 1)
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """SELECT COUNT(*) FROM spreads 
                   WHERE user_id = ? AND spread_type = ? 
                   AND created_at >= datetime('now', '-1 day')""",
                (user_id, spread_type)
            )
            row = await cursor.fetchone()
            count_today = row[0] if row else 0
            
            remaining = max(0, limit - count_today)
            can_use = remaining > 0
            
            return can_use, remaining
    
    async def get_next_reset_time(self) -> str:
        return "24 часа"
    
    async def get_referral_stats(self, user_id: int) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM users WHERE referred_by = ?",
                (user_id,)
            )
            invited_count = (await cursor.fetchone())[0]
            
            cursor = await db.execute(
                "SELECT COUNT(*) FROM payments WHERE package_type = 'referral_bonus' AND user_id = ?",
                (user_id,)
            )
            bonus_earned = (await cursor.fetchone())[0]
            
            return {
                "invited_count": invited_count,
                "bonus_earned": bonus_earned
            }
    
    async def process_referral(self, referrer_id: int, new_user_id: int) -> bool:
        if referrer_id == new_user_id:
            return False
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT referred_by FROM users WHERE user_id = ?",
                (new_user_id,)
            )
            row = await cursor.fetchone()
            
            if row and row[0] is not None:
                return False
            
            await db.execute(
                "UPDATE users SET referred_by = ? WHERE user_id = ?",
                (referrer_id, new_user_id)
            )
            await db.execute(
                "UPDATE users SET balance = balance + 1 WHERE user_id = ?",
                (referrer_id,)
            )
            await db.execute(
                "UPDATE users SET balance = balance + 1 WHERE user_id = ?",
                (new_user_id,)
            )
            
            for uid in [referrer_id, new_user_id]:
                await db.execute(
                    """INSERT INTO payments (user_id, package_type, spreads_added, amount_stars, telegram_charge_id) 
                       VALUES (?, 'referral_bonus', 1, 0, ?)""",
                    (uid, f"ref_{datetime.now().isoformat()}")
                )
            
            await db.commit()
            return True
    
    # ============================================
    # 🆕 НОВЫЕ МЕТОДЫ: Streak, Коллекция, Статистика
    # ============================================
    
    async def update_streak(self, user_id: int) -> dict:
        """🆕 Обновляет серию дней пользователя.
        Возвращает {"streak": N, "bonus_given": bool, "bonus_amount": X}
        """
        today = datetime.now().date().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT streak, last_spread_date FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return {"streak": 0, "bonus_given": False, "bonus_amount": 0}
            
            current_streak, last_date = row
            bonus_given = False
            bonus_amount = 0
            
            if last_date is None:
                # Первый расклад
                new_streak = 1
            elif last_date == today:
                # Уже был расклад сегодня — не увеличиваем
                new_streak = current_streak
            else:
                last = datetime.fromisoformat(last_date).date()
                diff = (datetime.now().date() - last).days
                
                if diff == 1:
                    # Вчера был расклад — продолжаем серию
                    new_streak = current_streak + 1
                    
                    # Бонус за серию: каждые 3 дня +1 расклад
                    if new_streak % 3 == 0:
                        bonus_amount = 1
                        await db.execute(
                            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                            (bonus_amount, user_id)
                        )
                        await db.execute(
                            """INSERT INTO payments (user_id, package_type, spreads_added, amount_stars, telegram_charge_id) 
                               VALUES (?, 'streak_bonus', ?, 0, ?)""",
                            (user_id, bonus_amount, f"streak_{today}")
                        )
                        bonus_given = True
                else:
                    # Пропуск — сбрасываем серию
                    new_streak = 1
            
            await db.execute(
                "UPDATE users SET streak = ?, last_spread_date = ? WHERE user_id = ?",
                (new_streak, today, user_id)
            )
            await db.commit()
            
            return {
                "streak": new_streak,
                "bonus_given": bonus_given,
                "bonus_amount": bonus_amount
            }
    
    async def get_streak(self, user_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT streak FROM users WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0
    
    async def get_card_collection(self, user_id: int) -> dict:
        """🆕 Возвращает коллекцию карт пользователя"""
        import json
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT cards FROM spreads WHERE user_id = ?",
                (user_id,)
            )
            rows = await cursor.fetchall()
            
            collected_ids = set()
            for row in rows:
                cards = json.loads(row[0])
                for card in cards:
                    collected_ids.add(card["id"])
            
            return {
                "collected": len(collected_ids),
                "total": 22,  # Старшие Арканы
                "percentage": round(len(collected_ids) / 22 * 100),
                "ids": collected_ids
            }
    
    async def get_most_used_category(self, user_id: int) -> Optional[str]:
        """🆕 Возвращает самую частую категорию пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """SELECT category, COUNT(*) as cnt 
                   FROM spreads 
                   WHERE user_id = ? 
                   GROUP BY category 
                   ORDER BY cnt DESC 
                   LIMIT 1""",
                (user_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else None
    
    async def get_recommended_spread(self, user_id: int) -> str:
        """🆕 Рекомендует расклад на основе истории"""
        async with aiosqlite.connect(self.db_path) as db:
            # Считаем, какие расклады уже делал
            cursor = await db.execute(
                """SELECT spread_type, COUNT(*) as cnt 
                   FROM spreads 
                   WHERE user_id = ? 
                   GROUP BY spread_type""",
                (user_id,)
            )
            rows = await cursor.fetchall()
            done_spreads = {row[0] for row in rows}
            
            # Приоритет рекомендации
            priority = [
                "past_present_future",  # Лёгкий платный
                "relationship",         # Средний
                "celtic_cross",         # Самый глубокий
            ]
            
            for spread in priority:
                if spread not in done_spreads:
                    return spread
            
            # Если всё пробовал — рекомендует самый популярный
            return "celtic_cross"
    
    async def get_admin_stats(self) -> dict:
        """🆕 Статистика для админа"""
        async with aiosqlite.connect(self.db_path) as db:
            # Всего пользователей
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            total_users = (await cursor.fetchone())[0]
            
            # Новых за сегодня
            cursor = await db.execute(
                """SELECT COUNT(*) FROM users 
                   WHERE created_at >= datetime('now', '-1 day')"""
            )
            new_today = (await cursor.fetchone())[0]
            
            # Новых за неделю
            cursor = await db.execute(
                """SELECT COUNT(*) FROM users 
                   WHERE created_at >= datetime('now', '-7 days')"""
            )
            new_week = (await cursor.fetchone())[0]
            
            # Раскладов сегодня
            cursor = await db.execute(
                """SELECT COUNT(*) FROM spreads 
                   WHERE created_at >= datetime('now', '-1 day')"""
            )
            spreads_today = (await cursor.fetchone())[0]
            
            # Платящих сегодня
            cursor = await db.execute(
                """SELECT COUNT(DISTINCT user_id), COALESCE(SUM(amount_stars), 0) 
                   FROM payments 
                   WHERE created_at >= datetime('now', '-1 day') 
                   AND package_type != 'referral_bonus' 
                   AND package_type != 'admin_bonus'
                   AND package_type != 'streak_bonus'"""
            )
            row = await cursor.fetchone()
            payers_today = row[0] if row else 0
            revenue_today = row[1] if row else 0
            
            # Общий доход
            cursor = await db.execute(
                """SELECT COUNT(*), COALESCE(SUM(amount_stars), 0) 
                   FROM payments 
                   WHERE package_type != 'referral_bonus' 
                   AND package_type != 'admin_bonus'
                   AND package_type != 'streak_bonus'"""
            )
            row = await cursor.fetchone()
            total_payers = row[0] if row else 0
            total_revenue = row[1] if row else 0
            
            # По уровням
            cursor = await db.execute(
                """SELECT level, COUNT(*) FROM users GROUP BY level"""
            )
            levels = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Активных (делали расклад за 7 дней)
            cursor = await db.execute(
                """SELECT COUNT(DISTINCT user_id) FROM spreads 
                   WHERE created_at >= datetime('now', '-7 days')"""
            )
            active_week = (await cursor.fetchone())[0]
            
            return {
                "total_users": total_users,
                "new_today": new_today,
                "new_week": new_week,
                "active_week": active_week,
                "spreads_today": spreads_today,
                "payers_today": payers_today,
                "revenue_today": revenue_today,
                "total_payers": total_payers,
                "total_revenue": total_revenue,
                "levels": levels
            }
    
    async def get_level_progress(self, user_id: int) -> dict:
        """🆕 Возвращает прогресс до следующего уровня"""
        user = await self.get_user(user_id)
        if not user:
            return {}
        
        total = user.get("total_spreads", 0)
        level = user.get("level", "Новичок")
        
        levels = [
            ("Новичок", 0, 5, "🌱"),
            ("Искатель", 5, 20, "🔍"),
            ("Маг", 20, 50, "🧙"),
            ("Верховный Жрец", 50, 999999, "👑"),
        ]
        
        for name, min_val, max_val, emoji in levels:
            if min_val <= total < max_val:
                progress = total - min_val
                needed = max_val - min_val
                percentage = int(progress / needed * 100) if needed < 999999 else 100
                
                # Найти следующий уровень
                next_level = None
                for n, mn, mx, em in levels:
                    if mn == max_val:
                        next_level = {"name": n, "emoji": em, "required": max_val}
                        break
                
                return {
                    "current": {"name": name, "emoji": emoji},
                    "next": next_level,
                    "progress": progress,
                    "needed": needed,
                    "percentage": percentage,
                    "total_spreads": total
                }
        
        return {}