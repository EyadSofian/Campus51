# ============================================================
# src/whatsapp_webhook.py
# ------------------------------------------------------------
# سيرفر FastAPI بيربط الـ agent بواتساب (Meta Cloud API).
#
# إزاي بيشتغل الموضوع:
#   1) Meta بيبعتلك رسائل المستخدمين على endpoint POST /webhook
#   2) إحنا بناخد نص الرسالة + رقم المرسل
#   3) نمرّرها للـ agent (thread_id = رقم التليفون → ذاكرة منفصلة لكل واحد)
#   4) رد البوت نبعته تاني لواتساب عن طريق Graph API
#
#   كمان Meta بيعمل GET /webhook مرة واحدة للتحقق (verification).
#
# التشغيل:
#   uvicorn src.whatsapp_webhook:app --host 0.0.0.0 --port 8000
# وبعدين expose بـ ngrok أو deploy على Railway وحط الـ URL عند Meta.
# ============================================================

import httpx
from fastapi import FastAPI, Request, Response, Query

from src.config import settings
from src.agent import build_agent

app = FastAPI(title="Campus 51 — Murshid WhatsApp Bot")

# بنبني الـ agent مرة واحدة عند تشغيل السيرفر (مش كل رسالة).
# ملاحظة: InMemorySaver معناها إن الذاكرة بتضيع لو السيرفر عمل restart.
# للإنتاج بدّلها بـ PostgresSaver (موضّح في agent.py + README).
agent = build_agent()

# Graph API base — رقم النسخة ممكن يتحدّث، v21.0 شغّال وقت الكتابة.
GRAPH_URL = f"https://graph.facebook.com/v21.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"


async def send_whatsapp_message(to: str, text: str) -> None:
    """يبعت رسالة نصية للمستخدم عن طريق WhatsApp Cloud API."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(GRAPH_URL, json=payload, headers=headers)
        if not resp.is_success:
            # نطبع الخطأ في اللوج بس مانكسرش السيرفر
            print(f"[whatsapp] فشل الإرسال {resp.status_code}: {resp.text}")


# ------------------------------------------------------------
# 1) التحقق (Verification) — Meta بينده GET مرة واحدة لما تضيف الـ webhook
# ------------------------------------------------------------
@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    # لازم نرجّع الـ challenge كـ plain text لو الـ token مظبوط
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=403)


# ------------------------------------------------------------
# 2) استقبال الرسائل — Meta بيبعت POST كل ما حد يبعت رسالة
# ------------------------------------------------------------
@app.post("/webhook")
async def receive_message(request: Request):
    data = await request.json()

    try:
        # بنية الـ payload بتاع Meta متداخلة شوية — بننقّب لحد الرسالة.
        entry = data["entry"][0]["changes"][0]["value"]

        # لو مفيش رسائل (مثلاً ده إشعار status) نتجاهل بهدوء.
        messages = entry.get("messages")
        if not messages:
            return {"status": "ignored"}

        message = messages[0]

        # بنتعامل بس مع الرسائل النصية في النسخة دي.
        if message.get("type") != "text":
            return {"status": "non-text ignored"}

        from_number = message["from"]           # رقم المرسل
        user_text = message["text"]["body"]      # نص الرسالة

    except (KeyError, IndexError):
        # أي شكل payload مش متوقع — نرجّع 200 عشان Meta ماـيعيدش الإرسال
        return {"status": "bad payload"}

    # --- نمرّر للـ agent ---
    # thread_id = رقم التليفون → كل مستخدم ليه ذاكرة لوحده.
    config = {"configurable": {"thread_id": from_number}}
    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_text}]},
        config=config,
    )
    reply = result["messages"][-1].content

    # --- نبعت الرد لواتساب ---
    await send_whatsapp_message(from_number, reply)

    # لازم نرجّع 200 بسرعة عشان Meta ماـيفتكرش إن فيه فشل.
    return {"status": "ok"}


@app.get("/")
async def health():
    """نقطة فحص بسيطة عشان تتأكد السيرفر شغّال."""
    return {"service": "Campus 51 Murshid WhatsApp Bot", "status": "running"}
