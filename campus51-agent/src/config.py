# ============================================================
# src/config.py
# ------------------------------------------------------------
# نقطة واحدة بنحمّل منها كل الإعدادات من ملف .env
# بدل ما نكرر os.getenv في كل مكان — ده بيخلّي الكود أنضف
# وأسهل في الصيانة (single source of truth).
# ============================================================

import os
from dotenv import load_dotenv

# load_dotenv بتقرأ ملف .env وتحط القيم في os.environ
# بنناديها مرة واحدة هنا، وباقي الملفات بتستورد من هنا.
load_dotenv()


class Settings:
    """كل إعدادات التطبيق في كلاس واحد منظّم."""

    # --- الموديل (LLM) ---
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-2.5-flash")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")

    # --- موديل الـ embeddings (للـ RAG) ---
    # gemini-embedding-001 هو الموديل الحالي المدعوم في الـ SDK الجديد.
    # لو فشل، الكود بيجرّب text-embedding-004 تلقائياً (fallback).
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")

    # --- Pinecone (vector store سحابي) ---
    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
    PINECONE_INDEX_NAME: str = os.getenv("PINECONE_INDEX_NAME", "campus51-kb")

    # --- Campus51 Lead Endpoint ---
    CAMPUS51_LEADS_ENDPOINT: str = os.getenv("CAMPUS51_LEADS_ENDPOINT", "")
    CAMPUS51_API_KEY: str = os.getenv("CAMPUS51_API_KEY", "")

    # --- WhatsApp Cloud API ---
    WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "")

    # --- مسارات ---
    KB_DIR: str = os.getenv("KB_DIR", "data/kb")

    def validate(self) -> None:
        """
        تحقّق إن المفاتيح الأساسية موجودة قبل ما نشغّل الـ agent.
        بترمي error واضح بدل ما الكود يقع بعدين برسالة غامضة.
        """
        missing = []
        if not self.GOOGLE_API_KEY:
            missing.append("GOOGLE_API_KEY")
        if not self.PINECONE_API_KEY:
            missing.append("PINECONE_API_KEY")
        if missing:
            raise RuntimeError(
                f"متغيرات ناقصة في .env: {', '.join(missing)}. "
                f"اعمل: cp .env.example .env  ثم املا القيم."
            )


# instance واحد بنستورده في كل مكان
settings = Settings()
