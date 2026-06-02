# ============================================================
# run_test.py
# ------------------------------------------------------------
# سكربت اختبار للـ CLI بيستخدم InMemoryVectorStore
# عشان نتجنب الحاجة لـ Pinecone في بيئة التطوير المحلية.
# للإنتاج: استخدم ingest.py مع Pinecone.
#
# التشغيل:
#   python run_test.py
# ============================================================

import logging
import sys
import time

# نشغّل logging عشان نشوف tool calls كاملة
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from pathlib import Path
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import settings
settings.validate()


def build_inmemory_store():
    """بيبني in-memory vector store من ملفات data/kb (للاختبار فقط)."""
    print("[test] بيبني in-memory vector store من data/kb...")
    kb_path = Path(settings.KB_DIR)
    md_files = sorted(kb_path.glob("*.md"))

    docs = []
    for f in md_files:
        text = f.read_text(encoding="utf-8")
        docs.append(Document(page_content=text, metadata={"source": f.name}))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=150,
        separators=["\n## ", "\n### ", "\n\n", "\n", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    print(f"[test] {len(docs)} ملف → {len(chunks)} chunk")

    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004",
        google_api_key=settings.GOOGLE_API_KEY,
    )
    store = InMemoryVectorStore(embedding=embeddings)
    store.add_documents(chunks)
    print(f"[test] ✅ الـ vector store جاهز ({len(chunks)} vector)")
    return store


# --- نبني الـ in-memory store ونحط محلّ Pinecone ---
import src.tools as tools_module

_store = build_inmemory_store()
tools_module._vector_store = _store


# --- نبني الـ agent وندير السيناريو ---
from src.agent import build_agent, chat_once

agent = build_agent()

# سيناريو الاختبار: سؤال عن كورس → ترشيح → lead capture → submit
print("\n" + "="*60)
print("  سيناريو الاختبار الكامل")
print("="*60 + "\n")

SCENARIO = [
    "مرحبا",
    "أنا مدرسة في مصر وعايزة أعرف أكثر عن برامج تطوير المعلمين عندكم",
    "أنا مهتمة بمسار QTS Pathway — ممكن توضحيلي أكثر؟",
    "تمام عايزة أسجل اهتمامي وفريقكم يتواصل معايا",
    "اسمي سارة أحمد",
    "مديرة مدرسة",
    "مصر",
    "sara.ahmed@school.edu",
    "01012345678",
    "QTS Pathway",
    "أيوه، ابعت بياناتي للفريق",
]

thread_id = "test-scenario-001"

for msg in SCENARIO:
    print(f"المستخدم: {msg}")
    t0 = time.monotonic()
    reply = chat_once(agent, msg, thread_id)
    elapsed = time.monotonic() - t0
    print(f"مرشد ({elapsed:.1f}s): {reply}")
    print("-" * 50)
    # استنى شوية عشان ما نحطش على الـ rate limit
    time.sleep(2)

print("\n✅ السيناريو اتنفذ بالكامل!")
