# مرشد (Murshid) — Campus 51 AI Advisor

نسختين من نفس البوت:
- **🟢 Production (عاجل):** بوت Botpress Cloud — تسليم العميل.
- **🔵 Learning:** نفس البوت مبني بـ **LangChain 1.0** — عشان تفهم الـ internals.

---

## 🗺️ الخطة الكاملة — مسارين بالتوازي

### المسار 1: تسليم العميل (Botpress Cloud) — أولوية

البوت اللي رفعته (`Morshed_-_2026_Jun_02.bpz`) **جاهز للـ import مباشرة**. مش محتاج تعيد بناءه — اعمل الآتي بالترتيب:

| # | الخطوة | التفاصيل |
|---|--------|----------|
| 1 | Import الـ bot | Botpress Cloud → New Bot → Import → ارفع `.bpz` |
| 2 | ارفع الـ KB | Knowledge Base → ارفع 14 ملف من `data/kb/` |
| 3 | Env variable | Settings → Environment Variables → `CAMPUS51_API_KEY` (اطلبه من شهاب) |
| 4 | تأكد من الـ variables | لازم الـ 7 موجودين: `leadName`, `leadRole`, `leadCountry`, `leadEmail`, `leadPhone`, `leadProgram`, `leadSuccess` |
| 5 | اربط WhatsApp | Channels → WhatsApp → Meta Cloud API (موضّح تحت) |
| 6 | Test | جرّب lead كامل + سؤال عن كورس |
| 7 | Publish | زرار Publish |

> **مهم:** الـ Execute Code في `submit_lead` بيبعت لـ:
> `https://campus51-auth-dot-plexiform-crane-421805.ey.r.appspot.com/api/chatbot-leads`
> بهيدر `X-API-Key`. تأكد إن الـ endpoint ده شغّال والـ key صح **قبل التسليم**.

### المسار 2: التعلّم (LangChain) — نفس البوت بالكود

تبنيه بنفسك وتفهم كل جزء بيعمل إيه. الخطوات تحت في قسم **التشغيل**.

---

## 🧩 خريطة المفاهيم: Botpress ↔ LangChain

ده أهم جدول للتعلّم — كل حاجة في Botpress ليها مقابل في الكود:

| Botpress (بتعرفه) | LangChain 1.0 (الكود) | الملف |
|---|---|---|
| Autonomous Node | `create_agent(...)` | `src/agent.py` |
| Guidelines / System Prompt | `system_prompt=` | `src/prompts.py` |
| "Search Knowledge" card | `@tool search_knowledge_base` | `src/tools.py` |
| الـ Knowledge Base نفسه | Chroma vector store + embeddings | `src/knowledge_base.py` |
| "Execute Code" (submit-lead) | `@tool submit_lead` | `src/tools.py` |
| `submitLead` transition | الموديل بينادي الـ tool لوحده | (داخل الـ agent loop) |
| Workflow Variables | arguments بتتبعت للـ tool | `src/tools.py` |
| ذاكرة المحادثة (تلقائي) | `checkpointer` + `thread_id` | `src/agent.py` |
| الـ Channel (WhatsApp) | FastAPI webhook | `src/whatsapp_webhook.py` |
| Model (Gemini 2.5 Flash) | `LLM_MODEL` env var | `.env` |

**الفرق الجوهري الوحيد:** في Botpress الـ transition حاجة منفصلة بتنقل لـ node. في LangChain مفيش nodes — الموديل بيقرر ينادي الأداة في نفس اللوب. أبسط وأنضف.

---

## 🏗️ المعمارية (LangChain version)

```
رسالة المستخدم (WhatsApp / CLI)
        │
        ▼
  ┌─────────────────┐
  │   create_agent   │  ← الموديل (Gemini) + الـ system prompt
  │  (agent loop)    │
  └────────┬─────────┘
           │ الموديل يقرر: أرد؟ ولا أنادي أداة؟
     ┌─────┴──────┐
     ▼            ▼
search_kb     submit_lead
(Chroma RAG)  (POST → Campus51)
     │            │
     └─────┬──────┘
           ▼
   النتيجة ترجع للموديل → يقرر تاني → لحد ما يرد رد نهائي
           │
           ▼
   الرد يترجّع للمستخدم
   (الـ checkpointer حافظ المحادثة بـ thread_id)
```

---

## ⚙️ التشغيل (LangChain version)

```bash
# 1) بيئة افتراضية + المكتبات
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2) الإعدادات
cp .env.example .env
# افتح .env وحط GOOGLE_API_KEY (من https://aistudio.google.com/apikey)

# 3) ابنِ الـ vector DB مرة واحدة
python ingest.py

# 4) جرّب من التيرمنال (ابدأ من هنا للتعلّم)
python -m src.cli

# 5) شغّل WhatsApp webhook (لما تجهّز Meta)
uvicorn src.whatsapp_webhook:app --host 0.0.0.0 --port 8000
```

---

## 📱 ربط WhatsApp (Meta Cloud API) — للنسختين

1. [Meta for Developers](https://developers.facebook.com) → Create App → نوع **Business**.
2. ضيف منتج **WhatsApp** → هتلاقي `Phone Number ID` و `Temporary Token`.
3. للإنتاج: اعمل **Permanent Token** عن طريق System User في Business Manager.
4. **Webhook setup:**
   - LangChain: deploy على Railway → URL = `https://your-app.up.railway.app/webhook`
   - Botpress: بياخد الربط من جوّه (Channels → WhatsApp) — أسهل، مفيش webhook يدوي.
5. حط `Verify Token` (أي نص تخترعه — نفسه في `.env`).
6. اشترك في حدث `messages`.

> **بديل أسرع لو العميل مش عايز Meta Business verification:** Evolution API (واتساب غير رسمي، QR-based — انت مستخدمه قبل كده). بس للعميل الرسمي، Meta Cloud API أأمن.

---

## 🚀 الإنتاج (production hardening)

النسخة دي **للتعلّم والتشغيل المباشر**. قبل ما تحطها production فعلي:

1. **الذاكرة الدائمة:** بدّل `InMemorySaver` بـ `PostgresSaver`
   (بتضيع الذاكرة دلوقتي لو السيرفر عمل restart — ده "durable state" اللي LangGraph 1.0 بيتكلم عنه):
   ```python
   from langgraph.checkpoint.postgres import PostgresSaver
   checkpointer = PostgresSaver.from_conn_string("postgresql://...")
   agent = build_agent(checkpointer=checkpointer)
   ```
2. **Pinecone بدل Chroma** لو الـ KB كبير (موضّح في `knowledge_base.py`).
3. **Rate limiting + signature verification** على الـ webhook (Meta بيوقّع الـ payloads).
4. **LangSmith** للـ observability (تشوف كل tool call والـ tokens) — انت مستخدمه قبل كده.
5. **Deploy:** Railway (الأسهل ليك) أو Hetzner/Coolify.

---

## 📂 بنية المشروع

```
campus51-agent/
├── README.md                  ← انت بتقراه دلوقتي
├── requirements.txt           ← مكتبات LangChain 1.0
├── .env.example               ← انسخه لـ .env واملاه
├── ingest.py                  ← يبني الـ vector DB (شغّله مرة)
├── data/kb/                   ← 14 ملف Knowledge Base
└── src/
    ├── config.py              ← الإعدادات (مكان واحد)
    ├── prompts.py             ← شخصية مرشد (System Prompt)
    ├── knowledge_base.py      ← RAG: بناء وتحميل الـ vector store
    ├── tools.py               ← الأداتين: search_kb + submit_lead
    ├── agent.py               ← create_agent + الذاكرة
    ├── cli.py                 ← تجربة تيرمنال (ابدأ من هنا)
    └── whatsapp_webhook.py    ← سيرفر FastAPI لواتساب
```

---

## 🎓 ابدأ من فين عشان تفهم؟

اقرا الملفات بالترتيب ده — كل واحد فيه كومنتس بتشرح السطور:
1. `prompts.py` — تشوف شخصية البوت (نفس بوتك بالظبط)
2. `tools.py` — تفهم الأداة = function + docstring
3. `knowledge_base.py` — تفهم الـ RAG بيشتغل إزاي
4. `agent.py` — تشوف إزاي الـ 3 حاجات بيتجمّعوا في سطر واحد
5. `cli.py` — شغّله وجرّب بنفسك
6. `whatsapp_webhook.py` — آخر حاجة، لما تبقى فاهم اللب
```
