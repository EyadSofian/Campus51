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
# embedding model: text-embedding-004 → dimension=768, metric=cosine
# ============================================================

import logging
from pathlib import Path
from time import sleep

from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from src.config import settings

logger = logging.getLogger(__name__)

# --- ثوابت الـ Pinecone index ---
_DIMENSION = 768        # حجم الـ vector لـ text-embedding-004
_METRIC = "cosine"      # مقياس التشابه الأنسب للنصوص
_CLOUD = "aws"
_REGION = "us-east-1"  # الـ region الافتراضي في الـ free tier


def _get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """
    موديل الـ embeddings — بيحوّل النص لأرقام.
    text-embedding-004: dimension=768، بيشتغل كويس مع العربي والإنجليزي.
    """
    # الـ google-genai SDK الجديد (4.x) بياخد الاسم بدون prefix "models/"
    return GoogleGenerativeAIEmbeddings(
        model="text-embedding-004",
        google_api_key=settings.GOOGLE_API_KEY,
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


def build_vector_store() -> PineconeVectorStore:
    """
    بيتنادى مرة واحدة (من ingest.py) عشان يبني الـ vector DB من الصفر.
    بيقرأ كل ملفات .md في data/kb، يقسّمها، ويرفعها على Pinecone.
    """
    kb_path = Path(settings.KB_DIR)
    md_files = sorted(kb_path.glob("*.md"))
    if not md_files:
        raise FileNotFoundError(f"مفيش ملفات .md في {kb_path.resolve()}")

    # --- 1) نقرأ الملفات ونحوّلها لـ Document objects ---
    # بنحط اسم الملف في metadata عشان نعرف المصدر بعدين (citation).
    docs: list[Document] = []
    for f in md_files:
        text = f.read_text(encoding="utf-8")
        docs.append(Document(page_content=text, metadata={"source": f.name}))

    # --- 2) نقسّم لـ chunks ---
    # chunk_size = حجم القطعة بالحروف. overlap = تداخل بين القطع
    # عشان الجملة اللي على الحدود ماتتقطعش معناها.
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n## ", "\n### ", "\n\n", "\n", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    print(f"[ingest] اتقرا {len(docs)} ملف، اتقسّموا لـ {len(chunks)} chunk")

    # --- 3) نتأكد من وجود الـ index ونرفع الـ vectors ---
    pc = _get_pinecone_client()
    _ensure_index_exists(pc)

    embeddings = _get_embeddings()
    vector_store = PineconeVectorStore.from_documents(
        documents=chunks,
        embedding=embeddings,
        index_name=settings.PINECONE_INDEX_NAME,
    )
    print(f"[ingest] ✅ الـ vector DB اترفع على Pinecone index: {settings.PINECONE_INDEX_NAME}")
    return vector_store


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
