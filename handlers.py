# handlers.py
from aiogram import Router, types
from aiogram.filters import Command
from datetime import datetime

from database import db
from admin_panel import router as admin_router

router = Router()
router.include_router(admin_router)

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🎮 <b>Cheat Panel Bot</b>\n\n"
        "📌 <b>Как активировать:</b>\n"
        "1. Запусти чит, он покажет HWID\n"
        "2. Купи ключ у админа\n"
        "3. Отправь: <code>/activate КЛЮЧ HWID</code>\n\n"
        "📝 <b>Пример:</b>\n"
        "<code>/activate A7F3D9C2B4E6F1A8 ABC123DEF456</code>\n\n"
        "🔍 <b>Команды:</b>\n"
        "/check - проверить статус\n"
        "/activate - активировать подписку",
        parse_mode="HTML"
    )

@router.message(Command("activate"))
async def cmd_activate(message: types.Message):
    args = message.text.split(maxsplit=2)
    
    if len(args) < 3:
        await message.answer(
            "❌ <b>Неверный формат!</b>\n\n"
            "Используй:\n"
            "<code>/activate КЛЮЧ HWID</code>\n\n"
            "Пример:\n"
            "<code>/activate A7F3D9C2B4E6F1A8 ABC123DEF456</code>",
            parse_mode="HTML"
        )
        return
    
    key = args[1].strip().upper()
    hwid = args[2].strip()
    
    wait_msg = await message.answer("🔄 Активирую...")
    
    success, result = await db.activate_with_key(
        message.from_user.id,
        message.from_user.username or "no_username",
        key,
        hwid
    )
    
    if success:
        await wait_msg.edit_text(
            f"✅ <b>Подписка активирована!</b>\n\n"
            f"🔑 HWID: <code>{hwid}</code>\n"
            f"📅 Действует до: {result}\n\n"
            f"🎮 Можешь использовать чит!",
            parse_mode="HTML"
        )
    else:
        await wait_msg.edit_text(f"❌ Ошибка: {result}")

@router.message(Command("check"))
async def cmd_check(message: types.Message):
    await message.answer(
        "📊 <b>Проверка статуса</b>\n\n"
        "Чит автоматически проверяет HWID при запуске.\n"
        "Если что-то не работает - обратись к админу.\n\n"
        "👑 Админ: @support",
        parse_mode="HTML"
    )