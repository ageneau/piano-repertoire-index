#!/usr/bin/env python3
"""Index sheet music PDFs from ~/Documents/Piano/Partitions/ into SQLite + ChromaDB.

Usage:
  ./index_scores.py                    # Full re-index
  ./index_scores.py --quick            # Filename-only (no OCR)
  ./index_scores.py --ocr              # Only update unknown catalogs via OCR
"""
import sqlite3, re, os, sys, json, io, pymupdf, pytesseract
from PIL import Image

BASE = os.path.expanduser("~/Documents/Piano/Partitions")
DB_PATH = "/home/BIG/src/DATA/YT/piano.db"
CHROMA_DIR = os.path.expanduser("~/.local/share/chroma")

# ── Patterns ─────────────────────────────────────────────────────────
BWV_PAT = re.compile(r'BWV\s*(\d+[a-zA-Z]?(?:/\d+)?)', re.IGNORECASE)
OPUS_PAT = re.compile(
    r'(?:(?:Op\.|Opus|op\.|OP\.)\s*(\d+)|(?:^|[\s_\-])[Oo][Pp]\s*(\d+)|(?:^|[\s_\-])op(\d{1,3}))'
    r'\s*(?:No\.|no\.|n[oô]\.?|nr\.?)?\s*(\d+)?', re.IGNORECASE)
K_PAT = re.compile(r'\b(K\.|KV|Köchel|Koechel)\s*(\d+)', re.IGNORECASE)
D_PAT = re.compile(r'\bD\.\s*(\d+)', re.IGNORECASE)
PIECE_TYPES = re.compile(r'\b(Prelude|Fugue|Sonata|Nocturne|Etude|Study|Waltz|Valse|Mazurka|Polonaise|'
    r'Ballade|Scherzo|Impromptu|Fantasy|Fantaisie|Rondo|Variations?|Concerto|Suite|Partita|'
    r'Invention|Sinfonia|Toccata|Prélude|Barcarolle|Gavotte|Gigue|Sarabande|Menuet|'
    r'Bourrée|Bourree|Allemande|Courante|Choral|Bagatelle|Intermezzo|Arabesque|Romance|'
    r'Sonatina)\b', re.IGNORECASE)
COMPOSERS = re.compile(r'\b(Bach|Beethoven|Chopin|Mozart|Liszt|Schumann|Schubert|Brahms|Debussy|Ravel|'
    r'Rachmaninoff|Tchaikovsky|Haydn|Handel|Haendel|Scarlatti|Clementi|Couperin|Satie|'
    r'Grieg|Albeniz|Burgmuller|Czerny|Pachelbel|Pescetti|Griboyedov|Gardel|Winston)\b', re.IGNORECASE)
COMPOSER_ALIASES = {"j.s. bach": "Bach", "js bach": "Bach", "bach": "Bach", "beethoven": "Beethoven",
    "chopin": "Chopin", "mozart": "Mozart", "debussy": "Debussy", "ravel": "Ravel",
    "schumann": "Schumann", "liszt": "Liszt", "schubert": "Schubert", "brahms": "Brahms",
    "haydn": "Haydn", "rachmaninoff": "Rachmaninoff", "satie": "Satie", "couperin": "Couperin",
    "clementi": "Clementi", "tchaikovsky": "Tchaikovsky", "pachebel": "Pachelbel",
    "haendel": "Handel", "griboyedov": "Griboyedov"}

def extract_catalog(text):
    clean = text.replace("_", " ").replace("-", " ").replace("–", " ")
    for pat in [(BWV_PAT, "BWV"), (D_PAT, "D"), (K_PAT, "K"), (OPUS_PAT, "Opus")]:
        m = pat[0].search(clean)
        if m:
            if pat[1] == "Opus":
                op = m.group(1) or m.group(2) or m.group(3) or ""
                no = m.group(4) or ""
                return (pat[1], f"{op}{' No.'+no if no else ''}")
            return (pat[1], m.group(1).lstrip('0') if pat[1] == "BWV" else m.group(1))
    return ("unknown", "unknown")

def normalize_composer(name):
    return COMPOSER_ALIASES.get(name.strip().lower(), name.strip().title())

conn = sqlite3.connect(DB_PATH)
conn.execute("DROP TABLE IF EXISTS scores")
conn.execute("""
    CREATE TABLE scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT, file_path TEXT UNIQUE, filename TEXT,
        composer_dir TEXT, composer TEXT, catalog_type TEXT DEFAULT 'unknown',
        catalog_number TEXT DEFAULT 'unknown', piece_name TEXT DEFAULT 'unknown',
        piece_type TEXT DEFAULT 'unknown', arranger TEXT DEFAULT 'unknown',
        genre TEXT DEFAULT 'unknown', is_compilation INTEGER DEFAULT 0, source TEXT
    )
""")

genre_map = {"jazz": "jazz", "films": "film", "musique_religieuse": "sacred",
             "ragtime": "ragtime", "solfege": "solfege"}
COMPILATION_WORDS = re.compile(r'\b(Complete|Collection|Anthology|Album|Book|Volume|Intros|Standards|Solos)\b', re.IGNORECASE)

scores = []
for root, dirs, files in os.walk(BASE):
    for f in files:
        if not f.lower().endswith('.pdf'): continue
        fp = os.path.join(root, f)
        rel = os.path.relpath(fp, BASE)
        parts = rel.split(os.sep)
        composer_dir = parts[0] if len(parts) > 1 else "unknown"
        name = os.path.splitext(f)[0]

        cat_type, cat_num = extract_catalog(name)
        piece_type = PIECE_TYPES.search(name.replace("_", " ").replace("-", " ")) 
        piece_type = piece_type.group(1) if piece_type else "unknown"
        is_comp = 1 if COMPILATION_WORDS.search(name) else 0

        composer = "unknown"
        mc = COMPOSERS.search(name)
        if mc: composer = mc.group(1).title()
        elif composer_dir != "unknown": composer = normalize_composer(composer_dir)
        else:
            mc = COMPOSERS.search(rel)
            if mc: composer = mc.group(1).title()

        genre = "unknown"
        for d in parts:
            g = genre_map.get(d.lower())
            if g: genre = g; break

        arranger = "unknown"
        am = re.search(r'[/\-–]\s*([A-Z][a-zéèêëàâäùûüôöîï]+)', name)
        if am: arranger = am.group(1)

        scores.append((fp, f, composer_dir, composer, cat_type, cat_num, "unknown",
                       piece_type, arranger, genre, is_comp, rel))

conn.executemany("INSERT OR REPLACE INTO scores (file_path, filename, composer_dir, composer, "
    "catalog_type, catalog_number, piece_name, piece_type, arranger, genre, is_compilation, source) "
    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", scores)
conn.commit()
print(f"Indexed {len(scores)} scores from filesystem")

# ── OCR pass ─────────────────────────────────────────────────────────
if "--quick" not in sys.argv:
    rows = conn.execute("""SELECT id, file_path, filename FROM scores 
        WHERE catalog_type='unknown' AND composer NOT IN ('pdf','unknown','Jazz','Films','Partitions - Autres')""").fetchall()
    print(f"OCR scanning {len(rows)} scores...")
    found = 0
    for rid, fp, fname in rows:
        if not os.path.exists(fp): continue
        try:
            doc = pymupdf.open(fp)
            text = doc[0].get_text().strip()
            if len(text) < 20:
                pix = doc[0].get_pixmap(dpi=200)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                text = pytesseract.image_to_string(img, lang='eng+fra')
            doc.close()
        except: continue

        ct, cn = extract_catalog(text)
        if ct != "unknown":
            conn.execute("UPDATE scores SET catalog_type=?, catalog_number=?, piece_name=? WHERE id=?",
                        (ct, cn, text[:100].replace('\n',' ').strip(), rid))
            found += 1
    conn.commit()
    print(f"OCR found {found} new catalog entries")

# ── ChromaDB ─────────────────────────────────────────────────────────
try:
    import chromadb
    from chromadb.config import Settings
    chroma_client = chromadb.PersistentClient(path=CHROMA_DIR, settings=Settings(anonymized_telemetry=False))
    conn.row_factory = sqlite3.Row
    try: chroma_client.delete_collection("scores")
    except: pass
    scol = chroma_client.create_collection("scores")

    scores = conn.execute("SELECT * FROM scores").fetchall()
    batch_size = 100
    for i in range(0, len(scores), batch_size):
        batch = scores[i:i+batch_size]
        docs, metas, sids = [], [], []
        for s in batch:
            clean = s["source"].replace(".pdf","").replace("_"," ").replace("  "," ")
            clean = clean.replace("kupdf.net ","").replace("IMSLP ","").replace("-"," ")
            parts = [clean]
            if s["composer"] not in ("unknown","pdf"): parts.append(s["composer"])
            if s["piece_name"] != "unknown": parts.append(s["piece_name"])
            if s["catalog_type"] != "unknown": parts.append(f"{s['catalog_type']} {s['catalog_number']}")
            if s["piece_type"] != "unknown": parts.append(s["piece_type"])
            docs.append(" | ".join(parts))
            metas.append({"type":"score","composer":s["composer"],"catalog_type":s["catalog_type"],
                "catalog_number":s["catalog_number"],"file_path":s["file_path"]})
            sids.append(str(s["id"]))
        scol.add(ids=sids, documents=docs, metadatas=metas)
    print(f"Chroma scores collection: {scol.count()} entries")
except ImportError:
    print("chromadb not installed, skipping vector index")

conn.close()
print("Done.")
