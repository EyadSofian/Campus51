# ============================================================
# ingest.py
# ------------------------------------------------------------
# سكربت بتشغّله مرة واحدة (أو كل ما تحدّث ملفات الـ KB)
# عشان يبني الـ vector DB في Pinecone من ملفات data/kb.
#
# التشغيل:
#   python ingest.py
#
# لازم تشغّله قبل ما تشغّل الـ agent (سواء CLI أو WhatsApp).
# ============================================================

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from src.config import settings
from src.knowledge_base import build_vector_store


if __name__ == "__main__":
    settings.validate()
    print(f"[ingest] بنقرا ملفات الـ KB من: {settings.KB_DIR}")
    print(f"[ingest] بنرفع على Pinecone index: {settings.PINECONE_INDEX_NAME}")
    build_vector_store()
    print("[ingest] ✅ تمام — الـ vector DB جاهز في Pinecone. دلوقتي شغّل:  python -m src.cli")
