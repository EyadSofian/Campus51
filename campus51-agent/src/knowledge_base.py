# ============================================================
# src/knowledge_base.py
# ------------------------------------------------------------
# ده الجزء اللي بيقابل "Search Knowledge" في Botpress.
#
# الفكرة (RAG = Retrieval Augmented Generation):
#   1) بنقسّم ملفات الـ KB لقطع صغيرة (chunks).
#   2) بنحوّل كل قطعة لـ vector (أرقام) عن طريق embedding model.
#   3) بنخزّنهم في Pinecone (vector DB سحابي).
#   4) وقت السؤال: بنحوّل السؤال لـ vector ونجيب أقرب القطع
#      (similarity search) ونرجّعها للموديل عشان يجاوب منها.
#
# embedding model: gemini-embedding-001 (768-dim via MRL truncation), metric=cosine
# ============================================================

import hashlib
import logging
from pathlib import Path
from time import sleep

from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_fixed,
)

from src.config import settings

logger = logging.getLogger(__name__)

# --- ثوابت الـ Pinecone index ---
_DIMENSION = 768        # حجم الـ vector لـ text-embedding-004
_METRIC = "cosine"      # مقياس التشابه الأنسب للنصوص
_CLOUD = "aws"
_REGION = "us-east-1"  # الـ region الافتراضي في الـ free tier

# --- إعدادات الرفع المتوافقة مع الـ free-tier quota ---
# gemini-embedding-001 على الـ free tier محدود بـ 100 embed request/دقيقة.
# علشان كده بنرفع على دفعات صغيرة، وبين كل دفعة وقفة بسيطة عشان نوزّع
# الطلبات على الدقيقة، ولو برضه اتعدّى الحد بنستنى دقيقة ونعيد الدفعة
# (retry على 429) بدل ما الـ ingest كله يقع ويدخل في loop.
_EMBED_BATCH_SIZE = 40   # عدد الـ chunks في الدفعة الواحدة (تحت الـ 100)
_BATCH_PAUSE = 35        # ثواني وقفة بين الدفعات (نوزّع على الدقيقة)
_RATE_LIMIT_WAIT = 63    # ثواني نستناها لو جالنا 429 (الكوتا بتتصفّر كل دقيقة)
_MAX_RATE_RETRIES = 6    # أقصى محاولات لكل دفعة قبل ما نستسلم


def _get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """
    موديل الـ embeddings — بيحوّل النص لأرقام.
    gemini-embedding-001: الموديل الرسمي الحالي. بديل text-embedding-004
    اللي اتعمله deprecated في 14 يناير 2026 وبقى بيرجّع 404 (ده كان سبب
    إن البوت مش بيجاوب على أسئلة الـ KB). بيشتغل كويس مع العربي والإنجليزي.

    ملاحظة مهمة عن الأبعاد:
      الـ default بتاع gemini-embedding-001 هو 3072، بس بيدعم MRL truncation.
      بنطلب 768 (output_dimensionality=_DIMENSION) عشان نفضل متوافقين مع الـ
      Pinecone index الـ 768. الـ cosine metric بيـ normalize تلقائياً فمش
      محتاجين normalization يدوي للأبعاد المقطوعة.
    """
    return GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-001",
        google_api_key=settings.GOOGLE_API_KEY,
        output_dimensionality=_DIMENSION,
    )


def _get_pinecone_client() -> Pinecone:
    """يرجّع Pinecone client مُعدّ بالـ API key."""
    return Pinecone(api_key=settings.PINECONE_API_KEY)


def _ensure_index_exists(pc: Pinecone) -> None:
    """
    بيتأكد إن الـ index موجود في Pinecone — لو مش موجود ينشئه.
    ServerlessSpec = بدون سيرفر مخصص (أرخص وأسرع للبدء).
    """
    index_name = settings.PINECONE_INDEX_NAME
    existing = [idx.name for idx in pc.list_indexes()]

    if index_name not in existing:
        logger.info("[pinecone] بينشئ index جديد: %s", index_name)
        pc.create_index(
            name=index_name,
            dimension=_DIMENSION,
            metric=_METRIC,
            spec=ServerlessSpec(cloud=_CLOUD, region=_REGION),
        )
        # بنستنى لحد ما الـ index يبقى ready
        for _ in range(30):
            status = pc.describe_index(index_name).status
            if status.get("ready"):
                break
            sleep(2)
        logger.info("[pinecone] ✅ الـ index جاهز: %s", index_name)
    else:
        logger.info("[pinecone] الـ index موجود بالفعل: %s", index_name)


def _load_and_split() -> list[Document]:
    """
    بيقرأ كل ملفات .md في data/kb ويقسّمها لـ chunks.
    عملية CPU بحتة (مفيش API) فينفع تتنادى أكتر من مرة بأمان.
    """
    kb_path = Path(settings.KB_DIR)
    md_files = sorted(kb_path.glob("*.md"))
    if not md_files:
        raise FileNotFoundError(f"مفيش ملفات .md في {kb_path.resolve()}")

    # بنحط اسم الملف في metadata عشان نعرف المصدر بعدين (citation).
    docs: list[Document] = []
    for f in md_files:
        text = f.read_text(encoding="utf-8")
        docs.append(Document(page_content=text, metadata={"source": f.name}))

    # chunk_size = حجم القطعة بالحروف. overlap = تداخل عشان الجملة اللي على
    # الحدود ماتتقطعش معناها.
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n## ", "\n### ", "\n\n", "\n", " ", ""],
    )
    return splitter.split_documents(docs)


def _chunk_id(doc: Document) -> str:
    """
    معرّف ثابت لكل chunk (اسم الملف + hash للمحتوى). ده بيخلّي الرفع
    idempotent: لو الـ ingest اتقطع في النص وأعاد، بنعمل upsert لنفس الـ ids
    فمنكرّرش vectors ومنفسدش الـ index — بنكمّل الناقص بس.
    """
    source = doc.metadata.get("source", "unknown")
    digest = hashlib.sha1(doc.page_content.encode("utf-8")).hexdigest()[:16]
    return f"{source}-{digest}"


def _is_quota_error(exc: Exception) -> bool:
    """بيتحقق إن الـ exception ده 429/quota من Gemini (free-tier embed limit)."""
    msg = str(exc).lower()
    return (
        "429" in msg
        or "resource_exhausted" in msg
        or "rate limit" in msg
        or "quota" in msg
    )


@retry(
    retry=retry_if_exception(_is_quota_error),
    wait=wait_fixed(_RATE_LIMIT_WAIT),
    stop=stop_after_attempt(_MAX_RATE_RETRIES),
    reraise=True,
)
def _upload_batch(
    store: PineconeVectorStore, docs: list[Document], ids: list[str]
) -> None:
    """
    بيرفع دفعة واحدة. لو جاله 429 (الكوتا خلصت) بيستنى دقيقة ويعيد —
    لأن الـ free-tier window بيتصفّر كل دقيقة. الـ ids الثابتة بتمنع التكرار
    لو الدفعة اتعادت.
    """
    store.add_documents(docs, ids=ids)


def expected_chunk_count() -> int:
    """عدد الـ chunks المتوقّع (unique ids) — بنقارن بيه عدد vectors في الـ index."""
    chunks = _load_and_split()
    return len({_chunk_id(c) for c in chunks})


def build_vector_store() -> PineconeVectorStore:
    """
    بيتنادى من ingest.py عشان يبني/يكمّل الـ vector DB.
    بيرفع على دفعات صغيرة محترماً الـ free-tier quota (100 embed/دقيقة)،
    وبـ ids ثابتة عشان يكون idempotent (ينفع يعيد من غير تكرار).
    """
    chunks = _load_and_split()
    ids = [_chunk_id(c) for c in chunks]
    total = len(chunks)
    print(f"[ingest] اتقسّموا لـ {total} chunk — هيترفعوا على دفعات من {_EMBED_BATCH_SIZE}")

    pc = _get_pinecone_client()
    _ensure_index_exists(pc)

    store = PineconeVectorStore(
        index_name=settings.PINECONE_INDEX_NAME,
        embedding=_get_embeddings(),
    )

    for start in range(0, total, _EMBED_BATCH_SIZE):
        batch_docs = chunks[start : start + _EMBED_BATCH_SIZE]
        batch_ids = ids[start : start + _EMBED_BATCH_SIZE]
        _upload_batch(store, batch_docs, batch_ids)
        done = min(start + _EMBED_BATCH_SIZE, total)
        print(f"[ingest] ✅ اترفع {done}/{total}")
        if done < total:
            sleep(_BATCH_PAUSE)  # نوزّع الطلبات على الدقيقة عشان منخبطش الـ quota

    print(f"[ingest] ✅ الـ vector DB جاهز على Pinecone index: {settings.PINECONE_INDEX_NAME}")
    return store


def current_vector_count() -> int:
    """
    عدد الـ vectors الحالي في الـ index (-1 لو مش موجود أو حصل خطأ).
    بنستخدمه عشان نعرف نكمّل الرفع ولا نعدّي.
    """
    try:
        pc = _get_pinecone_client()
        existing = [idx.name for idx in pc.list_indexes()]
        if settings.PINECONE_INDEX_NAME not in existing:
            return -1
        index = pc.Index(settings.PINECONE_INDEX_NAME)
        count = index.describe_index_stats().total_vector_count
        logger.info("[pinecone] الـ index فيه %d vector", count)
        return count
    except Exception as e:
        logger.warning("[pinecone] مقدرش يتحقق من الـ index: %s", e)
        return -1


def load_vector_store() -> PineconeVectorStore:
    """
    بيتنادى وقت التشغيل العادي — بيفتح الـ index الموجود في Pinecone
    (مش بيعيد رفع الـ vectors، عشان ده بياخد وقت وفلوس embeddings).
    """
    pc = _get_pinecone_client()
    existing = [idx.name for idx in pc.list_indexes()]
    if settings.PINECONE_INDEX_NAME not in existing:
        raise RuntimeError(
            f"الـ Pinecone index مش موجود: '{settings.PINECONE_INDEX_NAME}'. "
            f"شغّل الأول:  python ingest.py"
        )

    return PineconeVectorStore(
        index_name=settings.PINECONE_INDEX_NAME,
        embedding=_get_embeddings(),
    )
