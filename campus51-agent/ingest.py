# ============================================================
# ingest.py
# ------------------------------------------------------------
# بيشتغل تلقائياً عند كل startup قبل الـ uvicorn.
# بيتحقق الأول إن الـ index مش فيه data —
# لو فيه: بيعدّي بدون ما يعيد الرفع (سريع).
# لو فاضي: بيبني الـ KB كامل في Pinecone.
# ============================================================

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from src.config import settings
from src.knowledge_base import (
    build_vector_store,
    current_vector_count,
    expected_chunk_count,
)


if __name__ == "__main__":
    settings.validate()

    expected = expected_chunk_count()
    actual = current_vector_count()

    # نعدّي بس لو الـ index مكتمل فعلاً (actual >= expected).
    # لو ناقص (الرفع اتقطع في النص قبل كده) بنكمّل — الـ ids الثابتة في
    # build_vector_store بتمنع تكرار الـ vectors.
    if expected > 0 and actual >= expected:
        print(
            f"[ingest] ✅ الـ index '{settings.PINECONE_INDEX_NAME}' مكتمل "
            f"({actual}/{expected} vector) — skip."
        )
    else:
        print(
            f"[ingest] بنبني/نكمّل الـ KB في '{settings.PINECONE_INDEX_NAME}' "
            f"(عنده {max(actual, 0)} من {expected})..."
        )
        build_vector_store()
        print("[ingest] ✅ تمام — الـ vector DB جاهز. السيرفر هيبدأ دلوقتي...")
