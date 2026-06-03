# ============================================================
# src/agent.py
# ------------------------------------------------------------
# قلب المشروع: بنبني الـ agent باستخدام create_react_agent
# (الـ API الرسمي في LangGraph — الـ backbone بتاع LangChain 1.0).
#
# create_react_agent بياخد:
#   - model: موديل LLM جاهز (مش نص — عشان نقدر نضيف retry)
#   - tools: قايمة الأدوات
#   - prompt: شخصية وتعليمات البوت (SystemMessage)
#   - checkpointer: للذاكرة (يفتكر المحادثة لكل مستخدم)
#
# اللي بيحصل جوّه (مهم تفهمه):
#   المستخدم يبعت رسالة → الموديل يقرر: أرد على طول؟
#   ولا أنادي أداة؟ → لو نادى أداة، LangGraph ينفّذها
#   ويرجّع النتيجة للموديل → الموديل يقرر تاني...
#   اللوب ده بيكمّل لحد ما الموديل يرد رد نهائي بدون أدوات.
#   ده اسمه "agent loop" أو "ReAct loop".
# ============================================================

import logging

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent

from src.config import settings
from src.prompts import MURSHID_SYSTEM_PROMPT
from src.tools import ALL_TOOLS

logger = logging.getLogger(__name__)


def _build_llm() -> ChatGoogleGenerativeAI:
    """
    بيبني موديل Gemini جاهز لـ create_react_agent.

    max_retries=3 بيضيف retry تلقائي على 429 (rate limit) وأخطاء الشبكة
    على مستوى الـ HTTP client نفسه — ده الأنضف لأنه مابيلفّش الموديل
    في RunnableRetry (اللي كان بيكسر bind_tools اللي الـ agent محتاجه).
    """
    return ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=settings.LLM_TEMPERATURE,
        max_retries=3,
    )


def build_agent(checkpointer=None):
    """
    بيبني ويرجّع الـ agent جاهز للاستخدام.

    checkpointer = ذاكرة المحادثة.
      - InMemorySaver: في الرام (بتضيع لو السيرفر اتقفل) — كويس للتجربة.
      - للإنتاج: استخدم PostgresSaver أو SqliteSaver عشان تفضل بعد restart.
    """
    settings.validate()  # نتأكد المفاتيح موجودة قبل أي حاجة

    if checkpointer is None:
        checkpointer = InMemorySaver()

    llm = _build_llm()
    logger.info("[agent] بيبني الـ agent بـ model=%s", settings.LLM_MODEL)

    agent = create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        prompt=MURSHID_SYSTEM_PROMPT,   # system prompt ثابت لكل المحادثات
        checkpointer=checkpointer,
    )
    return agent


def chat_once(agent, user_text: str, thread_id: str) -> str:
    """
    helper بسيط: يبعت رسالة واحدة ويرجّع رد البوت كنص.

    thread_id = معرّف المحادثة. ده اللي بيخلّي كل مستخدم
    ليه ذاكرة منفصلة. في WhatsApp بنحط رقم التليفون هنا،
    فكل واحد بيكلّم البوت يكون ليه سياق لوحده.
    """
    logger.info("[agent:chat_once] thread_id=%r | msg=%r", thread_id, user_text[:80])

    # الـ config بتقول للـ checkpointer: ده تابع لأنهي محادثة
    config = {"configurable": {"thread_id": thread_id}}

    # بنبعت رسالة المستخدم. الـ agent بيضيفها لتاريخ المحادثة تلقائياً
    # (مش محتاجين نبعت التاريخ كله بنفسنا — الـ checkpointer بيعمل كده).
    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_text}]},
        config=config,
    )

    # result["messages"] فيها كل الرسائل. آخر واحدة هي رد البوت النهائي.
    reply = result["messages"][-1].content
    logger.info("[agent:chat_once] رد البوت: %r", reply[:120])
    return reply
