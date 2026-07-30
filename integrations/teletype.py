"""
Teletype App Integration (placeholder)

Когда получите API-ключ Teletype, раскомментируйте и настройте этот модуль.
Документация: https://teletype.app/api (уточните актуальную ссылку у Teletype)

Принцип работы:
  1. Teletype отправляет webhook на ваш эндпоинт при новом чате/сообщении
  2. Мы создаём Ticket в CRM автоматически
  3. Операторы видят новые обращения в боте

Для активации нужно:
  - Получить API ключ в настройках Teletype App
  - Добавить TELETYPE_API_KEY и TELETYPE_WEBHOOK_SECRET в .env
  - Раскомментировать код ниже
  - Добавить маршрут /webhook/teletype в FastAPI (см. api/webhooks.py)
"""

# import hmac
# import hashlib
# import aiohttp
# from typing import Optional
# from config import settings


# class TeletypeClient:
#     BASE_URL = "https://api.teletype.app"  # уточните актуальный URL
#
#     def __init__(self, api_key: str):
#         self.api_key = api_key
#         self.headers = {"Authorization": f"Bearer {api_key}"}
#
#     async def get_conversations(self, status: str = "open") -> list:
#         async with aiohttp.ClientSession() as session:
#             async with session.get(
#                 f"{self.BASE_URL}/conversations",
#                 headers=self.headers,
#                 params={"status": status},
#             ) as resp:
#                 return await resp.json()
#
#     async def send_message(self, conversation_id: str, text: str) -> dict:
#         async with aiohttp.ClientSession() as session:
#             async with session.post(
#                 f"{self.BASE_URL}/conversations/{conversation_id}/messages",
#                 headers=self.headers,
#                 json={"text": text},
#             ) as resp:
#                 return await resp.json()
#
#     @staticmethod
#     def verify_webhook(payload: bytes, signature: str, secret: str) -> bool:
#         expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
#         return hmac.compare_digest(expected, signature)


# async def handle_teletype_webhook(payload: dict, db_session) -> Optional[int]:
#     """
#     Обрабатывает входящий webhook от Teletype.
#     Возвращает ID созданного тикета или None.
#     """
#     from database.crud import create_ticket, get_operator_by_telegram_id
#
#     event_type = payload.get("event")
#     if event_type != "conversation.created":
#         return None
#
#     conversation = payload.get("conversation", {})
#     contact = conversation.get("contact", {})
#
#     # Назначаем системного оператора (или первого доступного)
#     # В будущем можно добавить логику роутинга
#
#     ticket = await create_ticket(
#         db_session,
#         operator_id=1,  # системный оператор
#         client_name=contact.get("name") or "Без имени",
#         client_phone=contact.get("phone"),
#         client_contact=contact.get("email") or conversation.get("channel"),
#         description=f"Из Teletype | ID: {conversation.get('id')}",
#     )
#     return ticket.id
