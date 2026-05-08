# database.py
import sqlite3
from datetime import datetime, timedelta
from typing import Tuple, Optional
from config import DATABASE

class Database:
    def __init__(self):
        self.conn = None
    
    async def init(self):
        """Инициализация базы данных и создание таблиц"""
        self.conn = sqlite3.connect(DATABASE)
        self.conn.row_factory = sqlite3.Row
        
        # Таблица пользователей
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                hwid TEXT UNIQUE,
                subscribed_until TIMESTAMP,
                license_key TEXT,
                is_active BOOLEAN DEFAULT 1,
                is_banned BOOLEAN DEFAULT 0,
                ban_reason TEXT,
                activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица ключей
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS license_keys (
                key TEXT PRIMARY KEY,
                plan TEXT,
                days INTEGER,
                expires_at TIMESTAMP,
                used_by INTEGER DEFAULT NULL,
                used_hwid TEXT DEFAULT NULL,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица заблокированных HWID
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS banned_hwid (
                hwid TEXT PRIMARY KEY,
                user_id INTEGER,
                reason TEXT,
                banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.conn.commit()
        return self
    
    def _execute(self, query: str, params: tuple = ()):
        """Выполнение запроса (синхронный метод для внутреннего использования)"""
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        self.conn.commit()
        return cursor
    
    async def execute(self, query: str, params: tuple = ()):
        """Асинхронная обёртка для execute"""
        return self._execute(query, params)
    
    async def fetchone(self, query: str, params: tuple = ()):
        """Получить одну запись"""
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()
    
    async def fetchall(self, query: str, params: tuple = ()):
        """Получить все записи"""
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
    
    # ========== HWID СИСТЕМА ==========
    
    async def check_hwid_access(self, hwid: str) -> Tuple[bool, str]:
        """
        Проверяет доступ по HWID для чита
        Возвращает: (доступ_разрешен, сообщение)
        """
        # Проверяем бан по HWID
        banned = await self.fetchone(
            "SELECT * FROM banned_hwid WHERE hwid = ?", 
            (hwid,)
        )
        if banned:
            return (False, f"HWID заблокирован. Причина: {banned['reason']}")
        
        # Ищем пользователя
        user = await self.fetchone(
            "SELECT * FROM users WHERE hwid = ?", 
            (hwid,)
        )
        
        if not user:
            return (False, "HWID не зарегистрирован")
        
        if user["is_banned"]:
            return (False, f"Пользователь заблокирован. Причина: {user['ban_reason']}")
        
        # Проверяем подписку
        if user["subscribed_until"]:
            until = datetime.fromisoformat(user["subscribed_until"])
            if until < datetime.now():
                return (False, "Срок подписки истёк")
        
        return (True, "Доступ разрешён")
    
    async def activate_with_key(self, user_id: int, username: str, key: str, hwid: str) -> Tuple[bool, str]:
        """
        Активация подписки по ключу с привязкой HWID
        Возвращает: (успех, сообщение_или_дата)
        """
        # Проверяем ключ
        key_info = await self.fetchone(
            "SELECT * FROM license_keys WHERE key = ?", 
            (key.upper(),)
        )
        
        if not key_info:
            return (False, "Ключ не найден")
        
        if key_info["used_by"] is not None:
            return (False, "Ключ уже использован")
        
        # Проверяем срок действия ключа
        if key_info["expires_at"]:
            expires = datetime.fromisoformat(key_info["expires_at"])
            if expires < datetime.now():
                return (False, "Срок действия ключа истёк")
        
        # Проверяем, не занят ли HWID
        existing = await self.fetchone(
            "SELECT user_id FROM users WHERE hwid = ? AND user_id != ?",
            (hwid, user_id)
        )
        if existing:
            return (False, "Этот HWID уже привязан к другому аккаунту")
        
        # Вычисляем новую дату подписки
        now = datetime.now()
        days = key_info["days"]
        new_until = now + timedelta(days=days)
        
        # Сохраняем пользователя
        await self.execute("""
            INSERT INTO users (user_id, username, hwid, subscribed_until, license_key, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                hwid = excluded.hwid,
                subscribed_until = excluded.subscribed_until,
                license_key = excluded.license_key,
                is_active = 1,
                is_banned = 0
        """, (user_id, username, hwid, new_until.isoformat(), key.upper()))
        
        # Помечаем ключ как использованный
        await self.execute(
            "UPDATE license_keys SET used_by = ?, used_hwid = ? WHERE key = ?",
            (user_id, hwid, key.upper())
        )
        
        return (True, new_until.strftime("%d.%m.%Y %H:%M"))
    
    # ========== АДМИН-ФУНКЦИИ ==========
    
    async def create_key(self, key: str, plan: str, days: int, created_by: int) -> bool:
        """Создаёт новый ключ"""
        expires = datetime.now() + timedelta(days=30)  # Ключ действителен 30 дней
        try:
            await self.execute(
                "INSERT INTO license_keys (key, plan, days, expires_at, created_by) VALUES (?, ?, ?, ?, ?)",
                (key, plan, days, expires.isoformat(), created_by)
            )
            return True
        except sqlite3.IntegrityError:
            return False
    
    async def delete_key(self, key: str) -> bool:
        """Удаляет ключ"""
        await self.execute("DELETE FROM license_keys WHERE key = ?", (key.upper(),))
        return True
    
    async def get_all_keys(self, limit: int = 50):
        """Получает все ключи"""
        return await self.fetchall(
            "SELECT * FROM license_keys ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
    
    async def ban_hwid(self, hwid: str, admin_id: int, reason: str) -> bool:
        """Блокирует HWID"""
        try:
            await self.execute(
                "INSERT INTO banned_hwid (hwid, user_id, reason) VALUES (?, ?, ?)",
                (hwid, admin_id, reason)
            )
            await self.execute(
                "UPDATE users SET is_banned = 1, ban_reason = ? WHERE hwid = ?",
                (reason, hwid)
            )
            return True
        except:
            return False
    
    async def unban_hwid(self, hwid: str) -> bool:
        """Разблокирует HWID"""
        await self.execute("DELETE FROM banned_hwid WHERE hwid = ?", (hwid,))
        await self.execute(
            "UPDATE users SET is_banned = 0, ban_reason = NULL WHERE hwid = ?",
            (hwid,)
        )
        return True
    
    async def clear_hwid(self, user_id: int) -> bool:
        """Очищает HWID у пользователя"""
        await self.execute(
            "UPDATE users SET hwid = NULL WHERE user_id = ?",
            (user_id,)
        )
        return True
    
    async def deactivate_subscription(self, hwid: str) -> bool:
        """Деактивирует подписку по HWID"""
        await self.execute(
            "UPDATE users SET subscribed_until = ? WHERE hwid = ?",
            (datetime.now().isoformat(), hwid)
        )
        return True
    
    async def get_all_users(self, limit: int = 50):
        """Получает всех пользователей"""
        return await self.fetchall(
            "SELECT * FROM users ORDER BY activated_at DESC LIMIT ?",
            (limit,)
        )
    
    async def get_stats(self) -> dict:
        """Получает статистику"""
        total_users = await self.fetchone("SELECT COUNT(*) as count FROM users")
        active_subs = await self.fetchone(
            "SELECT COUNT(*) as count FROM users WHERE subscribed_until > ? AND is_banned = 0",
            (datetime.now().isoformat(),)
        )
        banned = await self.fetchone("SELECT COUNT(*) as count FROM users WHERE is_banned = 1")
        total_keys = await self.fetchone("SELECT COUNT(*) as count FROM license_keys")
        used_keys = await self.fetchone("SELECT COUNT(*) as count FROM license_keys WHERE used_by IS NOT NULL")
        banned_hwid = await self.fetchone("SELECT COUNT(*) as count FROM banned_hwid")
        
        return {
            "total_users": total_users["count"],
            "active_subs": active_subs["count"],
            "banned_users": banned["count"],
            "total_keys": total_keys["count"],
            "used_keys": used_keys["count"],
            "banned_hwid": banned_hwid["count"]
        }

# Глобальный экземпляр БД
db = Database()