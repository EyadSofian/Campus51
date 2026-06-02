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
from src.knowledge_base import build_vector_store, is_index_populated


if __name__ == "__main__":
    settings.validate()

    if is_index_populated():
        print(f"[ingest] ✅ الـ Pinecone index '{settings.PINECONE_INDEX_NAME}' فيه data — skip.")
    else:
        print(f"[ingest] بنبني الـ KB في Pinecone index: {settings.PINECONE_INDEX_NAME}")
        build_vector_store()
        print("[ingest] ✅ تمام — الـ vector DB جاهز. السيرفر هيبدأ دلوقتي...")
