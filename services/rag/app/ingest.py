import os, re, hashlib, time, argparse
from pathlib import Path

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

# ---- Config ----
QDRANT_URL = os.getenv("QDRANT_HOST", "http://localhost:6333")
COLLECTION = "docs"
EMBED_MODEL_NAME = "BAAI/bge-m3"  # 1024 dims
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150

# ---- Conexiones ----
qdrant = QdrantClient(url=QDRANT_URL)
embed_model = SentenceTransformer(EMBED_MODEL_NAME)


# ---- Utilidades ----
def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8", errors="ignore")).hexdigest()

def norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def chunk_text(text: str, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    words = text.split()
    if not words:
        return []
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i+size])
        chunks.append(chunk)
        i += size - overlap
        if i < 0: break
    return chunks

# ---- Loaders por tipo ----
def read_txt(p: Path) -> str:
    import chardet
    data = p.read_bytes()
    enc = chardet.detect(data).get("encoding") or "utf-8"
    return data.decode(enc, errors="ignore")

def read_md(p: Path) -> str:
    return read_txt(p)

def read_pdf(p: Path) -> str:
    from pypdf import PdfReader
    reader = PdfReader(str(p))
    return "\n".join(page.extract_text() or "" for page in reader.pages)

def read_docx(p: Path) -> str:
    import docx
    doc = docx.Document(str(p))
    return "\n".join(par.text for par in doc.paragraphs)

def read_html(p: Path) -> str:
    from bs4 import BeautifulSoup
    html = read_txt(p)
    soup = BeautifulSoup(html, "html.parser")
    # Opcional: quita scripts/estilos
    for tag in soup(["script","style","noscript"]):
        tag.decompose()
    return soup.get_text(separator=" ")

READERS = {
    ".txt": read_txt,
    ".md": read_md,
    ".pdf": read_pdf,
    ".docx": read_docx,
    ".html": read_html,
    ".htm": read_html,
}

def discover_files(root: Path):
    exts = set(READERS.keys())
    for ext in exts:
        yield from root.rglob(f"*{ext}")

def ensure_collection():
    existing = [c.name for c in qdrant.get_collections().collections]
    if COLLECTION not in existing:
        qdrant.create_collection(
            collection_name=COLLECTION,
            vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE),
        )

def upsert_document(path: Path, base_dir: Path):
    ext = path.suffix.lower()
    reader = READERS.get(ext)
    if not reader:
        print(f"[skip] Extensión no soportada: {path.name}")
        return 0

    try:
        raw = reader(path)
    except Exception as e:
        print(f"[error] Leyendo {path.name}: {e}")
        return 0

    text = norm_ws(raw)
    if not text:
        print(f"[skip] Vacío: {path.name}")
        return 0

    rel_path = str(path.relative_to(base_dir))
    doc_id = sha1(rel_path)  # id estable por ruta relativa
    mtime = int(path.stat().st_mtime)

    chunks = chunk_text(text)
    if not chunks:
        print(f"[skip] Sin chunks: {path.name}")
        return 0

    points = []
    for idx, chunk in enumerate(chunks):
        vec = embed_model.encode(chunk).tolist()
        pid = int(sha1(f"{doc_id}-{idx}")[:16], 16)  # entero estable a partir de hash
        payload = {
            "text": chunk,
            "source": rel_path,
            "doc_id": doc_id,
            "chunk_id": idx,
            "mtime": mtime,
            "ext": ext,
            "title": path.stem,
        }
        points.append(models.PointStruct(id=pid, vector=vec, payload=payload))

    qdrant.upsert(collection_name=COLLECTION, points=points)
    print(f"[ok] {path.name}: {len(points)} chunks")
    return len(points)

def delete_by_doc_id(doc_id: str):
    # Elimina todos los puntos cuyo payload.doc_id == doc_id
    qdrant.scroll(
        collection_name=COLLECTION,  # touch para crear filtros
        limit=1
    )
    qdrant.delete(
        collection_name=COLLECTION,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[models.FieldCondition(
                    key="doc_id",
                    match=models.MatchValue(value=doc_id)
                )]
            )
        )
    )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default="/data", help="Carpeta con documentos a indexar")
    parser.add_argument("--clean-doc", default=None, help="doc_id para eliminar antes de reingestar")
    parser.add_argument("--recreate", action="store_true", help="Recrear colección (borra todo)")
    args = parser.parse_args()

    ensure_collection()
    if args.recreate:
        qdrant.delete_collection(COLLECTION)
        time.sleep(0.5)
        ensure_collection()
        print("[info] Colección recreada")

    base = Path(args.path)
    if not base.exists():
        print(f"[error] No existe {base}")
        return

    if args.clean_doc:
        delete_by_doc_id(args.clean_doc)
        print(f"[info] Eliminado doc_id={args.clean_doc}")

    total = 0
    for p in discover_files(base):
        total += upsert_document(p, base)
    print(f"[done] Total chunks: {total}")

if __name__ == "__main__":
    main()
