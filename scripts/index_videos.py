#!/usr/bin/env python3
"""Fetch metadata for video IDs and store in SQLite + ChromaDB.

Usage:
  ./index_videos.py piano.txt          # Index a playlist file
  ./index_videos.py --all              # Re-index all .txt files
  ./index_videos.py --rebuild          # Rebuild Chroma from existing DB
"""
import json, requests, time, sqlite3, re, os, sys, glob

TOKEN_PATH = os.path.expanduser("~/.hermes/google_token.json")
DB_PATH = "/home/BIG/src/DATA/YT/piano.db"
CHROMA_DIR = os.path.expanduser("~/.local/share/chroma")
DATA_DIR = "/home/BIG/src/DATA/YT"

# ── Classification patterns ──────────────────────────────────────────
TUTORIAL = re.compile(
    r'\b(tutorial|lesson|learn|how\s+to\s+play|exercises?|technique|practice|tips?|guide|'
    r'masterclass|cours|cour|leçon|apprendre|exercice|progresser|'
    r'méthode|methode|débutant|debutant|facile|easy|beginner|'
    r'ABRSM|RCM|grade\s*\d|teaching|teaches?|pedagogy|instruction|'
    r'analyse|analysis|workout|warm.up|'
    r'royal\s*conservatory|'
    r'mémoriser|memorize|memorising|conseil|astuce|comment|'
    r'teachers?\s+and\s+students?)\b', re.IGNORECASE)
PERFORMANCE = re.compile(
    r'\b(plays?|performs?|recital|live|concert|interprète|interprete|joue|interpretation|'
    r'rendition|covers?|version|recording|recorded|performed\s+by|played\s+by|'
    r'pianist|pianiste)\b', re.IGNORECASE)
GEAR = re.compile(
    r'\b(review|vs\.?|versus|amplification|keyboard|digital\s+piano|'
    r'headphones?|pedals?|ampli|sustain|stand|bench|assembly|'
    r'unboxing|buy|best\s+piano|top\s+\d+|comparison|compare)\b', re.IGNORECASE)
BWV_PAT = re.compile(r'BWV\s*(\d+[a-zA-Z]?(?:/\d+)?)', re.IGNORECASE)
OPUS_PAT = re.compile(r'(?:Op\.|Opus|op\.)\s*(\d+)\s*(?:No\.|no\.|n[oô]\.?|nr\.?)?\s*(\d+)?', re.IGNORECASE)
K_PAT = re.compile(r'\b(K\.|KV|Köchel|Koechel)\s*(\d+)', re.IGNORECASE)
COMPOSERS = re.compile(
    r'\b(Bach|Beethoven|Chopin|Mozart|Liszt|Schumann|Schubert|Brahms|Debussy|Ravel|Scriabin|'
    r'Rachmaninoff|Prokofiev|Stravinsky|Tchaikovsky|Haydn|Handel|Haendel|Vivaldi|Mendelssohn|'
    r'Grieg|Satie|Albeniz|Granados|Mompou|Scarlatti|Clementi|Czerny|Burgmuller|'
    r'Bartok|Kodaly|Ligeti|Messiaen|Poulenc|Faure|Saint.Saens|Couperin|Rameau|'
    r'Dvorak|Smetana|Glinka|Mussorgsky|Shostakovich|Kabalevsky|Pescetti|Griboyedov|Pachelbel|Gardel|Winston)\b', re.IGNORECASE)

def classify(title, desc):
    text = f"{title} {desc[:500]}"
    if re.search(r'\b(ABRSM|RCM|royal\s*conservatory)\b', text, re.IGNORECASE):
        return "tutorial"
    if TUTORIAL.search(text): return "tutorial"
    if GEAR.search(text): return "gear"
    if PERFORMANCE.search(text): return "performance"
    return "other"

def extract_catalog(title, desc):
    text = f"{title} {desc[:500]}"
    m = BWV_PAT.search(text)
    if m: return ("BWV", m.group(1).lstrip('0'))
    m = K_PAT.search(text)
    if m: return ("K", m.group(2))
    m = OPUS_PAT.search(text)
    if m:
        no = f" No. {m.group(2)}" if m.group(2) else ""
        return ("Opus", f"{m.group(1)}{no}")
    return ("unknown", "unknown")

def extract_composer(title, desc):
    m = COMPOSERS.search(f"{title} {desc[:300]}")
    return m.group(1).title() if m else "unknown"

# ── Setup DB ─────────────────────────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
conn.execute("""
    CREATE TABLE IF NOT EXISTS videos (
        id TEXT PRIMARY KEY, title TEXT, description TEXT,
        channel_id TEXT, channel_title TEXT, published_at TEXT,
        duration TEXT, tags TEXT, category_id TEXT,
        classification TEXT, catalog_type TEXT, catalog_number TEXT,
        composer TEXT, piece_name TEXT, video_url TEXT
    )
""")

# Collect video IDs
ids = set()
if "--rebuild" in sys.argv:
    existing = conn.execute("SELECT id FROM videos").fetchall()
    ids = set(r[0] for r in existing)
    print(f"Rebuilding from {len(ids)} existing videos")
elif "--all" in sys.argv:
    for txt in glob.glob(f"{DATA_DIR}/*.txt"):
        if txt.endswith("subscriptions.txt"):
            continue
        with open(txt) as f:
            ids.update(line.strip() for line in f if line.strip())
    print(f"Found {len(ids)} total video IDs from all playlists")
else:
    for arg in sys.argv[1:]:
        with open(arg) as f:
            ids.update(line.strip() for line in f if line.strip())
    print(f"Found {len(ids)} video IDs")

# Skip already indexed
with open(TOKEN_PATH) as f:
    tk = json.load(f)
headers = {"Authorization": f"Bearer {tk['token']}"}

existing_ids = set(r[0] for r in conn.execute("SELECT id FROM videos").fetchall())
new_ids = [vid for vid in ids if vid not in existing_ids]
print(f"New: {len(new_ids)}, Already indexed: {len(existing_ids)}")

fetched = 0
for i in range(0, len(new_ids), 50):
    batch = new_ids[i:i+50]
    r = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={"part": "snippet,contentDetails", "id": ",".join(batch)},
        headers=headers
    )
    data = r.json()
    if "error" in data:
        print(f"  API error: {data['error']['message']}")
        break
    rows = []
    for item in data.get("items", []):
        s = item.get("snippet", {})
        c = item.get("contentDetails", {})
        title = s.get("title", "")
        desc = s.get("description", "")
        cat_type, cat_num = extract_catalog(title, desc)
        composer = extract_composer(title, desc)
        cls = classify(title, desc)
        rows.append((
            item["id"], title, desc, s.get("channelId", ""),
            s.get("channelTitle", ""), s.get("publishedAt", ""),
            c.get("duration", ""), json.dumps(s.get("tags", [])),
            s.get("categoryId", ""), cls, cat_type, cat_num,
            composer, "unknown", f"https://youtu.be/{item['id']}"
        ))
    conn.executemany("""
        INSERT OR REPLACE INTO videos
        (id, title, description, channel_id, channel_title, published_at,
         duration, tags, category_id, classification, catalog_type,
         catalog_number, composer, piece_name, video_url)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)
    conn.commit()
    fetched += len(rows)
    print(f"  Batch {i//50+1}: {len(rows)} videos")
    time.sleep(0.3)

print(f"\nFetched {fetched} new videos. Total in DB: {conn.execute('SELECT COUNT(*) FROM videos').fetchone()[0]}")

# ── Update ChromaDB ──────────────────────────────────────────────────
try:
    import chromadb
    from chromadb.config import Settings
    chroma_client = chromadb.PersistentClient(path=CHROMA_DIR, settings=Settings(anonymized_telemetry=False))

    if "--rebuild" in sys.argv:
        # Explicit full rebuild
        try: chroma_client.delete_collection("videos")
        except: pass
        vcol = chroma_client.create_collection("videos")
        videos = conn.execute("SELECT * FROM videos").fetchall()
    elif new_ids:
        # Incremental: add only newly fetched videos
        try: vcol = chroma_client.get_collection("videos")
        except:
            vcol = chroma_client.create_collection("videos")
            videos = conn.execute("SELECT * FROM videos").fetchall()
            # Fall through to full add below
        else:
            placeholders = ",".join("?" for _ in new_ids)
            videos = conn.execute(f"SELECT * FROM videos WHERE id IN ({placeholders})", new_ids).fetchall()
    else:
        vcol = None

    if vcol:
        batch_size = 100
        for i in range(0, len(videos), batch_size):
            batch = videos[i:i+batch_size]
            docs, metas, vids = [], [], []
            for v in batch:
                docs.append(v["title"])
                metas.append({
                    "type": "video", "composer": v["composer"],
                    "catalog_type": v["catalog_type"], "catalog_number": v["catalog_number"],
                    "classification": v["classification"], "url": f"https://youtu.be/{v['id']}"
                })
                vids.append(v["id"])
            vcol.add(ids=vids, documents=docs, metadatas=metas)
        print(f"Chroma videos collection: {vcol.count()} entries")
    else:
        print("Chroma: no new videos, nothing to update")
except ImportError:
    print("chromadb not installed, skipping vector index")

conn.close()
