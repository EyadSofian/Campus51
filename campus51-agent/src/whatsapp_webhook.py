# ============================================================
# src/whatsapp_webhook.py
# ------------------------------------------------------------
# سيرفر FastAPI بيربط الـ agent بواتساب + ويب شات.
#
# الـ endpoints:
#   GET  /           → ويب شات UI (glassmorphism)
#   POST /api/chat   → API الويب شات (message → reply)
#   GET  /webhook    → التحقق من Meta
#   POST /webhook    → استقبال رسائل واتساب
#   GET  /health     → فحص حالة السيرفر
# ============================================================

import logging
import uuid

import httpx
from fastapi import FastAPI, Request, Response, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from src.config import settings
from src.agent import build_agent

logger = logging.getLogger(__name__)


def _is_quota_error(exc: Exception) -> bool:
    """429 / تجاوز الكوتا المجانية من Gemini (سواء الـ LLM أو الـ embeddings)."""
    m = str(exc).lower()
    return "429" in m or "resource_exhausted" in m or "quota" in m or "rate limit" in m


app = FastAPI(title="Campus 51 — Murshid")

# بنبني الـ agent مرة واحدة عند تشغيل السيرفر (مش كل رسالة).
agent = build_agent()

GRAPH_URL = f"https://graph.facebook.com/v21.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"


# ============================================================
# الويب شات
# ============================================================

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "webchat-default"


@app.get("/", response_class=HTMLResponse)
async def serve_chat_ui():
    """الويب شات UI — glassmorphism design."""
    return HTMLResponse(content=CHAT_HTML)


# ملاحظة: def (مش async) عن قصد — agent.invoke عملية blocking،
# فلو خلّيناها async هتقفل الـ event loop وممكن تسبب timeout/502.
# FastAPI بيشغّل الـ sync endpoints في threadpool فمفيش blocking.
@app.post("/api/chat")
def api_chat(body: ChatRequest):
    """API الويب شات: بياخد رسالة ويرجّع رد البوت."""
    logger.info("[webchat] thread=%r | msg=%r", body.thread_id, body.message[:80])
    config = {"configurable": {"thread_id": body.thread_id}}

    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": body.message}]},
            config=config,
        )
        reply = result["messages"][-1].content
        logger.info("[webchat] reply=%r", reply[:80])
        return {"reply": reply}

    except ValueError as e:
        # INVALID_CHAT_HISTORY: الـ thread فيه tool call معلّق — نبدأ thread جديد تماماً
        if "INVALID_CHAT_HISTORY" in str(e) or "ToolMessage" in str(e):
            fresh_id = "fresh-" + uuid.uuid4().hex[:8]
            logger.warning("[webchat] broken thread — retry بـ fresh thread %r", fresh_id)
            fresh_config = {"configurable": {"thread_id": fresh_id}}
            try:
                result = agent.invoke(
                    {"messages": [{"role": "user", "content": body.message}]},
                    config=fresh_config,
                )
                return {"reply": result["messages"][-1].content}
            except Exception:
                logger.exception("[webchat] fresh thread فشل كمان")
        logger.exception("[webchat] ValueError")
        return {"reply": "عذراً، حصل خطأ مؤقت. حاول مرة ثانية."}

    except Exception as e:
        # logger.exception بيطبع الـ traceback كامل في لوج Railway عشان نشوف السبب
        logger.exception("[webchat] error")
        if _is_quota_error(e):
            # ده السبب الأشهر: الكوتا المجانية اليومية لموديل Gemini خلصت
            return {"reply": (
                "⚠️ البوت وصل للحد اليومي المجاني من Google Gemini. "
                "لتشغيله بدون توقف فعّل الفوترة (billing) على مفتاح Google API، "
                "أو غيّر الموديل لـ gemini-2.5-flash-lite، أو جرّب لاحقاً."
            )}
        return {"reply": "عذراً، حصل خطأ في الاتصال بالخادم. حاول بعد لحظة."}


# ============================================================
# واتساب
# ============================================================

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
            logger.warning("[whatsapp] فشل الإرسال %d: %s", resp.status_code, resp.text)


@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """التحقق من Meta — بيتنادى مرة واحدة لما تضيف الـ webhook."""
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=403)


@app.post("/webhook")
async def receive_message(request: Request):
    """استقبال رسائل واتساب من Meta."""
    data = await request.json()
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        messages = entry.get("messages")
        if not messages:
            return {"status": "ignored"}
        message = messages[0]
        if message.get("type") != "text":
            return {"status": "non-text ignored"}
        from_number = message["from"]
        user_text = message["text"]["body"]
    except (KeyError, IndexError):
        return {"status": "bad payload"}

    # thread_id = رقم التليفون → ذاكرة منفصلة لكل مستخدم
    config = {"configurable": {"thread_id": from_number}}
    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_text}]},
        config=config,
    )
    reply = result["messages"][-1].content
    await send_whatsapp_message(from_number, reply)
    return {"status": "ok"}


@app.get("/health")
async def health():
    """فحص حالة السيرفر."""
    return {"service": "Campus 51 Murshid", "status": "running"}


@app.get("/diag")
def diag():
    """
    تشخيص سريع لحالة الـ KB — افتح اللينك ده في المتصفح:
        https://<your-app>.up.railway.app/diag

    بيقوللك: المفاتيح متظبطة؟ الـ Pinecone index فيه كام vector؟
    الـ search شغّال فعلاً ولا بيرمي خطأ إيه بالظبط.
    ده بيوضّح سبب "حصل خطأ في الاتصال" من غير ما تحتاج تبص في اللوج.
    """
    out = {
        "service": "Campus 51 Murshid",
        "google_key_set": bool(settings.GOOGLE_API_KEY),
        "pinecone_key_set": bool(settings.PINECONE_API_KEY),
        "index_name": settings.PINECONE_INDEX_NAME,
        "llm_model": settings.LLM_MODEL,
    }

    # حالة الـ Pinecone index (كام vector فيه مقابل المتوقّع)
    try:
        from src.knowledge_base import current_vector_count, expected_chunk_count
        out["vector_count"] = current_vector_count()
        out["expected_chunks"] = expected_chunk_count()
        out["index_ready"] = out["vector_count"] >= out["expected_chunks"] > 0
    except Exception as e:
        out["index_error"] = f"{type(e).__name__}: {e}"

    # اختبار search حي (نفس اللي البوت بيناديه)
    try:
        from src.tools import search_knowledge_base
        res = search_knowledge_base.invoke({"query": "نظام الدفع والتقسيط"})
        out["search_ok"] = True
        out["search_sample"] = (res or "")[:200]
    except Exception as e:
        out["search_ok"] = False
        out["search_error"] = f"{type(e).__name__}: {str(e)[:400]}"

    return out



# ============================================================
# ويب شات HTML (light theme — Tailwind + marked.js)
# ============================================================

CHAT_HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>مرشد | Campus 51</title>

<!-- مكتبات حديثة عبر CDN -->
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">

<script>
  // إعداد Tailwind: ألوان البراند + الخط
  tailwind.config = {
    theme: {
      extend: {
        fontFamily: { sans: ['Cairo', 'system-ui', 'sans-serif'] },
        colors: {
          brand: {
            50:'#eef2ff',100:'#e0e7ff',200:'#c7d2fe',300:'#a5b4fc',
            400:'#818cf8',500:'#6366f1',600:'#4f46e5',700:'#4338ca',
          },
        },
        keyframes: {
          pop: { '0%':{opacity:'0',transform:'translateY(10px) scale(.97)'},
                 '100%':{opacity:'1',transform:'translateY(0) scale(1)'} },
          bounceDot: { '0%,80%,100%':{transform:'translateY(0)',opacity:'.4'},
                       '40%':{transform:'translateY(-6px)',opacity:'1'} },
        },
        animation: {
          pop: 'pop .35s cubic-bezier(.34,1.56,.64,1)',
          'bounce-dot': 'bounceDot 1.3s ease infinite',
        },
      },
    },
  };
</script>

<style>
  /* تنعيم السكرول + شكل الـ scrollbar */
  #msgs::-webkit-scrollbar{ width:6px; }
  #msgs::-webkit-scrollbar-thumb{ background:#cbd5e1; border-radius:99px; }
  #msgs{ scroll-behavior:smooth; }

  /* تنسيق الماركداون جوّه فقاعة البوت */
  .md p{ margin:0 0 .5rem; } .md p:last-child{ margin-bottom:0; }
  .md ul{ margin:.25rem 0; padding-inline-start:1.25rem; list-style:disc; }
  .md ol{ margin:.25rem 0; padding-inline-start:1.25rem; list-style:decimal; }
  .md li{ margin:.15rem 0; }
  .md strong{ font-weight:700; color:#4338ca; }
  .md a{ color:#4f46e5; text-decoration:underline; }
  .md h1,.md h2,.md h3{ font-weight:700; margin:.4rem 0 .2rem; }
  .md code{ background:#eef2ff; padding:.1rem .35rem; border-radius:.35rem; font-size:.85em; }
</style>
</head>

<body class="font-sans bg-gradient-to-br from-slate-50 via-white to-indigo-50 min-h-screen flex items-center justify-center p-0 sm:p-4 text-slate-800">

  <!-- الحاوية الرئيسية -->
  <div class="w-full max-w-2xl h-screen sm:h-[92vh] sm:max-h-[880px] flex flex-col bg-white sm:rounded-3xl shadow-xl ring-1 ring-slate-900/5 overflow-hidden">

    <!-- الهيدر -->
    <header class="flex items-center gap-3 px-5 py-4 border-b border-slate-100 bg-white/80 backdrop-blur">
      <div class="relative">
        <div class="w-12 h-12 rounded-2xl bg-gradient-to-br from-brand-500 to-violet-500 grid place-items-center text-2xl shadow-lg shadow-brand-500/30">🎓</div>
        <span class="absolute -bottom-0.5 -left-0.5 w-3.5 h-3.5 bg-emerald-500 border-2 border-white rounded-full"></span>
      </div>
      <div class="flex-1">
        <h1 class="font-bold text-slate-900 leading-tight">مرشد</h1>
        <p class="text-xs text-slate-400">المستشار الأكاديمي · Campus 51</p>
      </div>
      <span class="text-[11px] font-semibold text-brand-600 bg-brand-50 ring-1 ring-brand-100 px-3 py-1.5 rounded-full">Campus 51</span>
    </header>

    <!-- منطقة الرسائل -->
    <main id="msgs" class="flex-1 overflow-y-auto px-4 sm:px-6 py-6 space-y-5 bg-slate-50/40">

      <!-- شاشة الترحيب -->
      <div id="welcome" class="text-center py-10">
        <div class="w-20 h-20 mx-auto mb-5 rounded-3xl bg-gradient-to-br from-brand-100 to-violet-100 ring-1 ring-brand-200 grid place-items-center text-4xl">🎓</div>
        <h2 class="text-lg font-bold text-slate-800">أهلاً بك في مرشد</h2>
        <p class="text-sm text-slate-500 mt-1 leading-relaxed">المستشار الأكاديمي الذكي لـ Campus 51<br>اسألني عن أي برنامج أو كورس أو مسار تأهيل</p>
        <div class="flex flex-wrap gap-2 justify-center mt-6">
          <button onclick="quick(this)" class="text-[13px] text-brand-700 bg-white hover:bg-brand-50 ring-1 ring-brand-200 hover:ring-brand-300 px-4 py-2 rounded-full transition">ما هو مسار QTS Pathway؟</button>
          <button onclick="quick(this)" class="text-[13px] text-brand-700 bg-white hover:bg-brand-50 ring-1 ring-brand-200 hover:ring-brand-300 px-4 py-2 rounded-full transition">ما هي البرامج المتاحة؟</button>
          <button onclick="quick(this)" class="text-[13px] text-brand-700 bg-white hover:bg-brand-50 ring-1 ring-brand-200 hover:ring-brand-300 px-4 py-2 rounded-full transition">أريد التسجيل في دورة</button>
          <button onclick="quick(this)" class="text-[13px] text-brand-700 bg-white hover:bg-brand-50 ring-1 ring-brand-200 hover:ring-brand-300 px-4 py-2 rounded-full transition">معلومات عن الشهادات</button>
        </div>
      </div>

    </main>

    <!-- مؤشر الكتابة -->
    <div id="typing" class="hidden px-4 sm:px-6 pb-2">
      <div class="flex items-end gap-2.5">
        <div class="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-500 to-violet-500 grid place-items-center text-sm shrink-0">🎓</div>
        <div class="bg-white ring-1 ring-slate-100 rounded-2xl rounded-br-md px-4 py-3 flex gap-1.5">
          <span class="w-2 h-2 bg-brand-300 rounded-full animate-bounce-dot"></span>
          <span class="w-2 h-2 bg-brand-300 rounded-full animate-bounce-dot" style="animation-delay:.18s"></span>
          <span class="w-2 h-2 bg-brand-300 rounded-full animate-bounce-dot" style="animation-delay:.36s"></span>
        </div>
      </div>
    </div>

    <!-- منطقة الإدخال -->
    <footer class="px-4 sm:px-6 py-4 border-t border-slate-100 bg-white">
      <div class="flex items-end gap-2 bg-slate-100 focus-within:bg-white focus-within:ring-2 focus-within:ring-brand-300 ring-1 ring-slate-200 rounded-2xl px-3 py-2 transition">
        <textarea id="inp" rows="1" placeholder="اكتب رسالتك هنا..."
          class="flex-1 bg-transparent outline-none resize-none max-h-32 text-[15px] leading-relaxed py-1.5 placeholder:text-slate-400"></textarea>
        <button id="send" onclick="send()"
          class="w-11 h-11 rounded-xl bg-gradient-to-br from-brand-500 to-violet-500 text-white grid place-items-center shrink-0 hover:scale-105 active:scale-95 transition disabled:opacity-40 disabled:hover:scale-100 shadow-lg shadow-brand-500/30">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
      <p class="text-[11px] text-slate-400 text-center mt-2.5">Enter للإرسال · Shift+Enter لسطر جديد · مدعوم بـ Google Gemini</p>
    </footer>
  </div>

<script>
  const tid = 'web-' + Math.random().toString(36).slice(2, 9);
  const msgs = document.getElementById('msgs');
  const typing = document.getElementById('typing');
  const inp = document.getElementById('inp');
  const sendBtn = document.getElementById('send');

  marked.setOptions({ breaks: true });

  inp.addEventListener('input', () => {
    inp.style.height = 'auto';
    inp.style.height = Math.min(inp.scrollHeight, 128) + 'px';
  });
  inp.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });

  const now = () => new Date().toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' });

  function addMsg(role, text, isErr = false) {
    document.getElementById('welcome')?.remove();
    const isBot = role === 'bot';
    const row = document.createElement('div');
    row.className = 'flex items-end gap-2.5 animate-pop ' + (isBot ? '' : 'flex-row-reverse');

    const avatar = isBot
      ? '<div class="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-500 to-violet-500 grid place-items-center text-sm shrink-0">🎓</div>'
      : '<div class="w-8 h-8 rounded-xl bg-gradient-to-br from-sky-400 to-blue-500 grid place-items-center text-sm shrink-0">👤</div>';

    const bubbleBase = 'max-w-[78%] px-4 py-2.5 text-[14.5px] leading-relaxed shadow-sm';
    const bubble = isBot
      ? (isErr
          ? '<div class="' + bubbleBase + ' bg-rose-50 text-rose-600 ring-1 ring-rose-100 rounded-2xl rounded-br-md">' + escapeHtml(text) + '</div>'
          : '<div class="' + bubbleBase + ' md bg-white text-slate-700 ring-1 ring-slate-100 rounded-2xl rounded-br-md">' + marked.parse(text) + '</div>')
      : '<div class="' + bubbleBase + ' bg-gradient-to-br from-brand-500 to-violet-500 text-white rounded-2xl rounded-bl-md">' + escapeHtml(text) + '</div>';

    row.innerHTML = avatar +
      '<div class="flex flex-col ' + (isBot ? 'items-start' : 'items-end') + '">' +
        bubble +
        '<span class="text-[10px] text-slate-300 mt-1 px-1">' + now() + '</span>' +
      '</div>';
    msgs.appendChild(row);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function escapeHtml(t) {
    const d = document.createElement('div');
    d.textContent = t;
    return d.innerHTML;
  }

  function showTyping() {
    typing.classList.remove('hidden');
    msgs.parentNode.insertBefore(typing, msgs.nextSibling);
    msgs.scrollTop = msgs.scrollHeight;
  }
  function hideTyping() { typing.classList.add('hidden'); }

  function quick(el) { inp.value = el.textContent; send(); }

  async function send() {
    const txt = inp.value.trim();
    if (!txt || sendBtn.disabled) return;
    inp.value = ''; inp.style.height = 'auto';
    sendBtn.disabled = true;
    addMsg('user', txt);
    showTyping();
    try {
      const r = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: txt, thread_id: tid }),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const d = await r.json();
      hideTyping();
      addMsg('bot', d.reply);
    } catch (e) {
      hideTyping();
      addMsg('bot', '⚠️ حصل خطأ في الاتصال، حاول مرة ثانية.', true);
    } finally {
      sendBtn.disabled = false;
      inp.focus();
    }
  }
</script>
</body>
</html>"""
