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

import httpx
from fastapi import FastAPI, Request, Response, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from src.config import settings
from src.agent import build_agent

logger = logging.getLogger(__name__)

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


@app.post("/api/chat")
async def api_chat(body: ChatRequest):
    """API الويب شات: بياخد رسالة ويرجّع رد البوت."""
    logger.info("[webchat] thread=%r | msg=%r", body.thread_id, body.message[:80])
    config = {"configurable": {"thread_id": body.thread_id}}
    result = agent.invoke(
        {"messages": [{"role": "user", "content": body.message}]},
        config=config,
    )
    reply = result["messages"][-1].content
    logger.info("[webchat] reply=%r", reply[:80])
    return {"reply": reply}


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


# ============================================================
# ويب شات HTML (glassmorphism)
# ============================================================

CHAT_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>مرشد | Campus 51</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}

body{
  font-family:'Cairo',system-ui,sans-serif;
  background:#060d1f;
  min-height:100vh;
  display:flex;
  align-items:center;
  justify-content:center;
  overflow:hidden;
  position:relative;
}

/* خلفية متحركة */
.orb{
  position:fixed;border-radius:50%;
  filter:blur(90px);opacity:.18;
  pointer-events:none;
  animation:drift 12s ease-in-out infinite;
}
.o1{width:600px;height:600px;background:radial-gradient(circle,#4f46e5,#7c3aed);top:-150px;left:-150px;animation-delay:0s}
.o2{width:500px;height:500px;background:radial-gradient(circle,#0ea5e9,#6366f1);bottom:-120px;right:-120px;animation-delay:-5s}
.o3{width:350px;height:350px;background:radial-gradient(circle,#8b5cf6,#ec4899);top:40%;left:35%;animation-delay:-9s}

@keyframes drift{
  0%,100%{transform:translate(0,0) scale(1)}
  33%{transform:translate(40px,-40px) scale(1.05)}
  66%{transform:translate(-30px,25px) scale(.95)}
}

/* شبكة خلفية */
body::before{
  content:'';position:fixed;inset:0;
  background-image:
    linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),
    linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px);
  background-size:60px 60px;pointer-events:none;z-index:0;
}

/* الحاوية الرئيسية */
.chat-wrap{
  width:100%;max-width:800px;
  height:95vh;max-height:920px;
  margin:0 16px;
  display:flex;flex-direction:column;
  background:rgba(255,255,255,.038);
  backdrop-filter:blur(28px);-webkit-backdrop-filter:blur(28px);
  border:1px solid rgba(255,255,255,.09);
  border-radius:28px;
  overflow:hidden;
  box-shadow:
    0 40px 80px rgba(0,0,0,.5),
    inset 0 1px 0 rgba(255,255,255,.1),
    inset 0 0 0 1px rgba(255,255,255,.04);
  position:relative;z-index:1;
}

/* هيدر */
.header{
  padding:18px 26px;
  background:rgba(255,255,255,.045);
  border-bottom:1px solid rgba(255,255,255,.07);
  display:flex;align-items:center;gap:14px;
  flex-shrink:0;
}

.h-logo{
  width:50px;height:50px;border-radius:16px;
  background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 50%,#a855f7 100%);
  display:flex;align-items:center;justify-content:center;
  font-size:24px;flex-shrink:0;
  box-shadow:0 6px 20px rgba(99,102,241,.45);
}

.h-text{flex:1}
.h-name{
  font-size:18px;font-weight:700;color:#f1f5f9;
  display:flex;align-items:center;gap:8px;
}
.h-sub{font-size:12px;color:rgba(255,255,255,.4);margin-top:3px}

.h-dot{
  width:9px;height:9px;background:#22c55e;border-radius:50%;
  box-shadow:0 0 0 3px rgba(34,197,94,.2);
  animation:hbeat 2s infinite;
}
@keyframes hbeat{
  0%,100%{box-shadow:0 0 0 3px rgba(34,197,94,.2)}
  50%{box-shadow:0 0 0 6px rgba(34,197,94,0)}
}

.h-badge{
  padding:7px 16px;
  background:rgba(99,102,241,.12);
  border:1px solid rgba(99,102,241,.28);
  border-radius:20px;
  font-size:11.5px;font-weight:600;
  color:#a5b4fc;letter-spacing:.4px;
}

/* منطقة الرسائل */
.msgs{
  flex:1;overflow-y:auto;
  padding:28px 26px 16px;
  display:flex;flex-direction:column;gap:18px;
  scroll-behavior:smooth;
}
.msgs::-webkit-scrollbar{width:3px}
.msgs::-webkit-scrollbar-thumb{background:rgba(255,255,255,.08);border-radius:2px}

/* فقاعات الرسائل */
.msg{
  display:flex;gap:10px;align-items:flex-end;
  animation:popIn .35s cubic-bezier(.34,1.56,.64,1);
}
@keyframes popIn{
  from{opacity:0;transform:translateY(18px) scale(.93)}
  to{opacity:1;transform:translateY(0) scale(1)}
}

.msg.user{flex-direction:row-reverse}

.m-av{
  width:34px;height:34px;border-radius:11px;
  display:flex;align-items:center;justify-content:center;
  font-size:15px;flex-shrink:0;margin-bottom:3px;
}
.msg.bot .m-av{background:linear-gradient(135deg,#6366f1,#8b5cf6)}
.msg.user .m-av{background:linear-gradient(135deg,#0ea5e9,#3b82f6)}

.m-body{max-width:72%}

.m-bubble{
  padding:14px 18px;
  border-radius:20px;
  font-size:14.5px;line-height:1.85;
  white-space:pre-wrap;word-break:break-word;
}

.msg.bot .m-bubble{
  background:rgba(99,102,241,.1);
  border:1px solid rgba(99,102,241,.18);
  border-bottom-right-radius:5px;
  color:#e2e8f0;
}
.msg.user .m-bubble{
  background:rgba(14,165,233,.12);
  border:1px solid rgba(14,165,233,.22);
  border-bottom-left-radius:5px;
  color:#f1f5f9;text-align:right;
}

.m-time{
  font-size:10px;color:rgba(255,255,255,.28);
  margin-top:5px;padding:0 3px;
}
.msg.user .m-time{text-align:left}

/* مؤشر الكتابة */
.typing{
  display:none;align-items:flex-end;gap:10px;
}
.typing.on{display:flex;animation:popIn .3s ease}

.t-dots{
  background:rgba(99,102,241,.1);
  border:1px solid rgba(99,102,241,.18);
  border-radius:20px;border-bottom-right-radius:5px;
  padding:14px 18px;
  display:flex;gap:6px;align-items:center;
}
.t-d{
  width:7px;height:7px;background:rgba(165,180,252,.7);
  border-radius:50%;
  animation:tdot 1.3s ease infinite;
}
.t-d:nth-child(2){animation-delay:.22s}
.t-d:nth-child(3){animation-delay:.44s}
@keyframes tdot{
  0%,60%,100%{transform:translateY(0);opacity:.5}
  30%{transform:translateY(-7px);opacity:1}
}

/* رسالة ترحيب */
.welcome{
  text-align:center;padding:40px 20px;
  color:rgba(255,255,255,.45);
  font-size:13.5px;line-height:2;
}
.w-icon{
  width:72px;height:72px;
  background:linear-gradient(135deg,rgba(99,102,241,.2),rgba(139,92,246,.2));
  border:1px solid rgba(99,102,241,.25);
  border-radius:22px;
  display:flex;align-items:center;justify-content:center;
  font-size:36px;
  margin:0 auto 18px;
  backdrop-filter:blur(8px);
}
.w-title{font-size:17px;font-weight:700;color:#e2e8f0;margin-bottom:8px}

/* اقتراحات سريعة */
.suggestions{
  display:flex;flex-wrap:wrap;gap:8px;
  justify-content:center;margin-top:18px;
}
.sug{
  padding:8px 16px;
  background:rgba(99,102,241,.1);
  border:1px solid rgba(99,102,241,.22);
  border-radius:20px;
  font-size:12.5px;color:#c4b5fd;
  cursor:pointer;
  transition:all .2s;
}
.sug:hover{
  background:rgba(99,102,241,.2);
  border-color:rgba(99,102,241,.4);
  transform:translateY(-1px);
}

/* منطقة الإدخال */
.input-zone{
  padding:16px 26px 20px;
  background:rgba(255,255,255,.03);
  border-top:1px solid rgba(255,255,255,.06);
  flex-shrink:0;
}
.inp-wrap{
  display:flex;gap:10px;align-items:flex-end;
  background:rgba(255,255,255,.055);
  border:1px solid rgba(255,255,255,.09);
  border-radius:18px;
  padding:10px 10px 10px 16px;
  transition:border-color .25s,box-shadow .25s;
}
.inp-wrap:focus-within{
  border-color:rgba(99,102,241,.45);
  box-shadow:0 0 0 4px rgba(99,102,241,.07);
}

#msgIn{
  flex:1;background:none;border:none;outline:none;
  color:#f1f5f9;
  font-family:'Cairo',system-ui,sans-serif;
  font-size:14.5px;line-height:1.6;
  resize:none;max-height:130px;min-height:26px;
  padding:4px 0;direction:auto;
}
#msgIn::placeholder{color:rgba(255,255,255,.22)}

#sendBtn{
  width:42px;height:42px;border-radius:13px;border:none;
  background:linear-gradient(135deg,#6366f1,#8b5cf6);
  color:#fff;cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  transition:all .2s;flex-shrink:0;
}
#sendBtn:hover:not(:disabled){
  transform:scale(1.08);
  box-shadow:0 6px 20px rgba(99,102,241,.55);
}
#sendBtn:active:not(:disabled){transform:scale(.94)}
#sendBtn:disabled{opacity:.35;cursor:not-allowed}

.inp-hint{
  font-size:10.5px;color:rgba(255,255,255,.18);
  margin-top:8px;text-align:center;
}

/* فوتر */
.footer{
  padding:10px 26px 14px;
  text-align:center;
  font-size:10.5px;color:rgba(255,255,255,.15);
  flex-shrink:0;
}

/* خطأ */
.err-bubble{
  background:rgba(239,68,68,.1)!important;
  border-color:rgba(239,68,68,.22)!important;
  color:#fca5a5!important;
}

@media(max-width:600px){
  .chat-wrap{margin:0;border-radius:0;height:100vh;max-height:none}
  .msgs{padding:16px}
  .input-zone{padding:12px 14px 16px}
  .header{padding:14px 16px}
  .h-badge{display:none}
}
</style>
</head>
<body>
<div class="orb o1"></div>
<div class="orb o2"></div>
<div class="orb o3"></div>

<div class="chat-wrap">
  <!-- هيدر -->
  <div class="header">
    <div class="h-logo">🎓</div>
    <div class="h-text">
      <div class="h-name">مرشد <div class="h-dot"></div></div>
      <div class="h-sub">المستشار الأكاديمي · Campus 51</div>
    </div>
    <div class="h-badge">Campus 51</div>
  </div>

  <!-- الرسائل -->
  <div class="msgs" id="msgs">
    <div class="welcome" id="welcome">
      <div class="w-icon">🎓</div>
      <div class="w-title">أهلاً بك في مرشد</div>
      المستشار الأكاديمي الذكي لـ Campus 51<br>
      اسألني عن أي برنامج أو كورس أو مسار تأهيل
      <div class="suggestions">
        <span class="sug" onclick="quickSend(this)">ما هو مسار QTS Pathway؟</span>
        <span class="sug" onclick="quickSend(this)">ما هي البرامج المتاحة؟</span>
        <span class="sug" onclick="quickSend(this)">أريد التسجيل في دورة</span>
        <span class="sug" onclick="quickSend(this)">معلومات عن الشهادات</span>
      </div>
    </div>
  </div>

  <!-- مؤشر الكتابة -->
  <div class="typing" id="typing">
    <div class="m-av" style="background:linear-gradient(135deg,#6366f1,#8b5cf6);margin-bottom:3px">🎓</div>
    <div class="t-dots">
      <div class="t-d"></div><div class="t-d"></div><div class="t-d"></div>
    </div>
  </div>

  <!-- إدخال -->
  <div class="input-zone">
    <div class="inp-wrap">
      <textarea id="msgIn" placeholder="اكتب رسالتك هنا..." rows="1"></textarea>
      <button id="sendBtn" onclick="send()">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2.5"
          stroke-linecap="round" stroke-linejoin="round">
          <line x1="22" y1="2" x2="11" y2="13"/>
          <polygon points="22 2 15 22 11 13 2 9 22 2"/>
        </svg>
      </button>
    </div>
    <div class="inp-hint">Enter للإرسال &nbsp;·&nbsp; Shift+Enter لسطر جديد</div>
  </div>

  <div class="footer">مدعوم بـ Google Gemini &nbsp;·&nbsp; Campus 51 &copy; 2026</div>
</div>

<script>
const tid = 'web-' + Math.random().toString(36).slice(2,9);
const msgs = document.getElementById('msgs');
const typing = document.getElementById('typing');
const inp = document.getElementById('msgIn');
const btn = document.getElementById('sendBtn');

inp.addEventListener('input',()=>{
  inp.style.height='auto';
  inp.style.height=Math.min(inp.scrollHeight,130)+'px';
});
inp.addEventListener('keydown',e=>{
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}
});

function ts(){
  return new Date().toLocaleTimeString('ar-EG',{hour:'2-digit',minute:'2-digit'});
}

function addMsg(role,text,err=false){
  const w=document.getElementById('welcome');
  if(w)w.remove();

  const d=document.createElement('div');
  d.className='msg '+role;

  const av=role==='bot'?'🎓':'👤';
  const ec=err?' err-bubble':'';

  d.innerHTML=`
    <div class="m-av">${av}</div>
    <div class="m-body">
      <div class="m-bubble${ec}">${esc(text)}</div>
      <div class="m-time">${ts()}</div>
    </div>`;
  msgs.appendChild(d);
  scrollEnd();
}

function esc(t){
  return t
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;')
    .replace(/\\n/g,'<br>');
}

function scrollEnd(){msgs.scrollTop=msgs.scrollHeight}

function showTyping(){
  typing.classList.add('on');
  msgs.parentNode.insertBefore(typing,msgs.nextSibling);
  scrollEnd();
}
function hideTyping(){typing.classList.remove('on')}

function quickSend(el){
  inp.value=el.textContent;
  send();
}

async function send(){
  const txt=inp.value.trim();
  if(!txt||btn.disabled)return;
  inp.value='';inp.style.height='auto';
  btn.disabled=true;
  addMsg('user',txt);
  showTyping();
  try{
    const r=await fetch('/api/chat',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:txt,thread_id:tid})
    });
    if(!r.ok)throw new Error('HTTP '+r.status);
    const d=await r.json();
    hideTyping();
    addMsg('bot',d.reply);
  }catch(e){
    hideTyping();
    addMsg('bot','⚠️ حصل خطأ في الاتصال، حاول مرة ثانية.',true);
  }finally{
    btn.disabled=false;inp.focus();
  }
}
</script>
</body>
</html>"""
