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


def _env(key: str, default: str = "") -> str:
    """
    بيقرأ متغير من البيئة و بيشيل أي مسافات/أسطر زيادة (.strip()).
    ده مهم جداً: لو حطّيت مفتاح أو اسم موديل بمسافة زيادة في الآخر
    (شائع جداً مع الـ copy-paste على Railway)، الـ strip بيمنعها
    من إنها تكسر اسم الموديل أو الـ API key.
    """
    return os.getenv(key, default).strip()


class Settings:
    """كل إعدادات التطبيق في كلاس واحد منظّم."""

    # --- الموديل (LLM) ---
    LLM_MODEL: str = _env("LLM_MODEL", "gemini-2.5-flash")
    LLM_TEMPERATURE: float = float(_env("LLM_TEMPERATURE", "0.3") or "0.3")
    GOOGLE_API_KEY: str = _env("GOOGLE_API_KEY")

    # --- موديل الـ embeddings (للـ RAG) ---
    # gemini-embedding-001 هو الموديل الحالي المدعوم في الـ SDK الجديد.
    # لو فشل، الكود بيجرّب text-embedding-004 تلقائياً (fallback).
    EMBEDDING_MODEL: str = _env("EMBEDDING_MODEL", "gemini-embedding-001")

    # --- Pinecone (vector store سحابي) ---
    PINECONE_API_KEY: str = _env("PINECONE_API_KEY")
    PINECONE_INDEX_NAME: str = _env("PINECONE_INDEX_NAME", "campus51-kb")

    # --- Campus51 Lead Endpoint ---
    CAMPUS51_LEADS_ENDPOINT: str = _env("CAMPUS51_LEADS_ENDPOINT")
    CAMPUS51_API_KEY: str = _env("CAMPUS51_API_KEY")

    # --- WhatsApp Cloud API ---
    WHATSAPP_TOKEN: str = _env("WHATSAPP_TOKEN")
    WHATSAPP_PHONE_NUMBER_ID: str = _env("WHATSAPP_PHONE_NUMBER_ID")
    WHATSAPP_VERIFY_TOKEN: str = _env("WHATSAPP_VERIFY_TOKEN")

    # --- مسارات ---
    KB_DIR: str = _env("KB_DIR", "data/kb")

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
