# Embedding Index

A local semantic search index over the wiki. Optional — use when the
wiki grows beyond ~200 pages and keyword grep is no longer sufficient.

## Choice: SQLite-vec vs Chroma

| Option | Pros | Cons |
|--------|------|------|
| **sqlite-vec** | Zero-install (just a Python extension), single file, no server, Git-friendly | Requires building or pip-installing the extension |
| **Chroma** | Simpler Python API, more features | Persistent directory can grow large, requires `pip install chromadb` |
| **FAISS** | Fast, battle-tested | No built-in persistence, more setup |

Recommended: **sqlite-vec** for the default wiki setup. Single file
(`wiki/_embeddings.sqlite`), no server, easy to rebuild.

## Setup

```bash
pip install sqlite-vec sentence-transformers
```

## Building the index

Claude can build the index by running a Python snippet via Bash:

```python
import sqlite3
import sqlite_vec
from pathlib import Path
from sentence_transformers import SentenceTransformer

MODEL = SentenceTransformer("all-MiniLM-L6-v2")
DB = Path("wiki/_embeddings.sqlite")
DB.unlink(missing_ok=True)

conn = sqlite3.connect(DB)
conn.enable_load_extension(True)
sqlite_vec.load(conn)
conn.execute("CREATE VIRTUAL TABLE pages USING vec0(embedding float[384])")
conn.execute("CREATE TABLE meta (rowid INTEGER PRIMARY KEY, path TEXT, title TEXT)")

for md in Path("wiki").rglob("*.md"):
    if md.name.startswith("_"):
        continue
    text = md.read_text(encoding="utf-8")
    emb = MODEL.encode(text[:8000]).tolist()
    cur = conn.execute("INSERT INTO meta (path, title) VALUES (?, ?)", (str(md), md.stem))
    conn.execute("INSERT INTO pages (rowid, embedding) VALUES (?, ?)", (cur.lastrowid, str(emb)))

conn.commit()
```

## Query

```python
q_emb = MODEL.encode(question).tolist()
rows = conn.execute(
    "SELECT path, title, distance FROM pages JOIN meta USING(rowid) "
    "WHERE embedding MATCH ? ORDER BY distance LIMIT 5",
    (str(q_emb),),
).fetchall()
```

## When to rebuild

- After any ingest that creates 10+ pages
- During lint if page count grew >10% since last build
- When the user asks to "refresh the index"

## Gitignore

Add to `.gitignore`:
```
wiki/_embeddings.sqlite
wiki/_embeddings/
```

The index is rebuildable from the wiki source, so it should not be
committed.
