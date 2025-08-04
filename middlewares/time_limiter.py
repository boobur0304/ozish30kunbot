from aiogram import BaseMiddleware
from aiogram.types import Message
from datetime import datetime, time
from typing import Callable, Awaitable, Dict, Any

# Ruxsat berilgan vaqtlar
ALLOWED_START = time(6, 30)   # 06:30
ALLOWED_END = time(22, 30)    # 22:30

class TimeLimiterMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        now = datetime.now().time()

        if not (ALLOWED_START <= now <= ALLOWED_END):
            await event.answer("⛔️ Bot faqat 06:30 dan 22:30 gacha ishlaydi.\nIltimos, shu vaqt oralig‘ida qayta urinib ko‘ring.")
            return

        return await handler(event, data)
