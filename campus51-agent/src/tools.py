# ============================================================
# src/tools.py
# ------------------------------------------------------------
# هنا بنعرّف الأدوات (Tools) اللي الـ agent ينفع ينادي عليها.
# دول بالظبط نفس أداتين Botpress:
#   1) search_knowledge_base  ←→  "Search Knowledge" card
#   2) submit_lead            ←→  "Execute Code (submit-lead)" card
#
# في LangChain الأداة = function عادية متزيّنة بـ @tool.
# أهم حاجة: الـ docstring! الموديل بيقراه عشان يفهم
# الأداة بتعمل إيه وامتى يستخدمها. اكتبه كويس.
# ============================================================

import logging
import time

import httpx
from langchain_core.tools import tool
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from src.config import settings
from src.knowledge_base import load_vector_store

logger = logging.getLogger(__name__)

# بنحمّل الـ vector store مرة واحدة عند تشغيل التطبيق (مش كل سؤال)
# عشان نوفّر وقت. لو لسه ماعملتش ingest هيرمي error واضح.
_vector_store = None


def _get_store():
    """lazy loading — مانفتحش الـ DB غير أول مرة نحتاجه فعلاً."""
    global _vector_store
    if _vector_store is None:
        _vector_store = load_vector_store()
    return _vector_store


def _is_rate_limit_error(exc: Exception) -> bool:
    """بيتحقق إن الـ exception ده 429 Rate Limit من Gemini أو Pinecone."""
    msg = str(exc).lower()
    return "429" in msg or "rate limit" in msg or "resource_exhausted" in msg or "quota" in msg


@tool
def search_knowledge_base(query: str) -> str:
    """
    Search the official Campus 51 knowledge base for accurate information about
    courses, programs, the QTS pathway, instructors, certifications, accreditation,
    payment methods, refunds, and enrollment.

    Use this for ANY factual question about Campus 51 before answering.
    The query should be the user's question or relevant keywords (Arabic or English).

    Returns the most relevant passages from the knowledge base.
    """
    logger.info("[tool:search_knowledge_base] query=%r", query)
    start = time.monotonic()

    # similarity_search بترجّع أقرب k قطعة للسؤال.
    # k=4 توازن كويس بين التغطية وعدم إغراق الموديل بنص كتير.
    results = _get_store().similarity_search(query, k=4)

    elapsed = time.monotonic() - start
    logger.info("[tool:search_knowledge_base] رجع %d نتيجة في %.2fs", len(results), elapsed)

    if not results:
        return "No relevant information found in the knowledge base."

    # بنرجّع النص + اسم الملف المصدر (عشان الموديل يقدر يسمّي البرنامج).
    blocks = []
    for i, doc in enumerate(results, 1):
        source = doc.metadata.get("source", "unknown")
        blocks.append(f"[Source {i}: {source}]\n{doc.page_content}")
    return "\n\n---\n\n".join(blocks)


@retry(
    retry=retry_if_exception(_is_rate_limit_error),
    wait=wait_exponential(multiplier=1, min=5, max=60),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _post_lead_with_retry(payload: dict) -> httpx.Response:
    """
    بيبعت الـ lead للـ endpoint مع retry تلقائي على 429 (rate limit).
    tenacity بيستنى وقت أطول كل محاولة (exponential backoff).
    """
    return httpx.post(
        settings.CAMPUS51_LEADS_ENDPOINT,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": settings.CAMPUS51_API_KEY,
        },
        timeout=15.0,
    )


@tool
def submit_lead(
    name: str,
    role: str,
    country: str,
    email: str,
    phone: str,
    program_of_interest: str,
) -> str:
    """
    Submit a qualified lead to the Campus 51 sales team.

    Call this ONLY after collecting all the lead fields AND the user has
    explicitly confirmed they want their details sent to the team.

    Required minimum: name and email. Other fields may be empty strings if
    the user declined to provide them.

    Returns a success or failure message.
    """
    logger.info(
        "[tool:submit_lead] name=%r email=%r program=%r",
        name, email, program_of_interest,
    )

    # ده نفس payload وnفس الـ headers بالظبط اللي في Botpress Execute Code.
    payload = {
        "name": name or "",
        "role": role or "",
        "country": country or "",
        "email": email or "",
        "phone": phone or "",
        "program_of_interest": program_of_interest or "",
    }

    try:
        response = _post_lead_with_retry(payload)

        if response.is_success:  # أي 2xx
            logger.info("[tool:submit_lead] ✅ نجح الإرسال")
            return "SUCCESS: Lead submitted to the Campus 51 team."
        else:
            # بنرجّع الكود للموديل عشان يعرف يعتذر بأدب للمستخدم
            logger.warning("[tool:submit_lead] فشل %d", response.status_code)
            return (
                f"FAILED: endpoint returned {response.status_code}. "
                f"Tell the user to contact info@campus51.com directly."
            )

    except Exception as err:
        # أي خطأ شبكة — مانكسرش الـ agent، نرجّع رسالة يتصرف بيها
        logger.error("[tool:submit_lead] error: %s", err)
        return (
            f"ERROR submitting lead: {err}. "
            f"Tell the user to contact info@campus51.com directly."
        )


# قايمة الأدوات اللي هنسلّمها للـ agent
ALL_TOOLS = [search_knowledge_base, submit_lead]
