# Piano Video & Score Index

Index YouTube piano playlists and local sheet music, extract piece
metadata (composer, BWV, Opus), and match videos to scores.

## Data Pipeline

```
YouTube API         .txt (IDs)       SQLite (metadata)       ChromaDB (vectors)
   │                    │                   │                      │
   ▼                    ▼                   ▼                      ▼
fetch_playlist →  piano.txt  →  index_videos  →  videos collection
                              piano.db:          all-MiniLM-L6-v2
                              videos table       video titles
                                                    
~/Documents/                                scores collection
Piano/Partitions/ →  index_scores  →      score filenames + metadata
                   piano.db:
                   scores table

                         match.py ←──────────────────┘
                         (cross-modal search)
```

## Database — `~/.local/share/piano-repertoire-index/piano.db`

Single SQLite file, two tables, no relations between them. Matching
is done via ChromaDB vectors, not SQL joins.

### `videos` — YouTube video metadata

| Column | Type | How it's set |
|--------|------|-------------|
| id | TEXT PK | YouTube video ID |
| title | TEXT | From API |
| description | TEXT | From API (full text) |
| channel_id | TEXT | From API |
| channel_title | TEXT | From API |
| published_at | TEXT | ISO 8601 |
| duration | TEXT | ISO 8601 duration (`PT12M34S`) |
| tags | TEXT | JSON array |
| category_id | TEXT | YouTube category number |
| classification | TEXT | `tutorial` / `performance` / `gear` / `other` — set by keyword regex on title + first 500 chars of description |
| catalog_type | TEXT | `BWV` / `Opus` / `K` / `D` / `unknown` — set by regex on title |
| catalog_number | TEXT | e.g. `846`, `28 No. 4`, `543` |
| composer | TEXT | Detected from title/description — falls back to `unknown` |
| piece_name | TEXT | Extracted piece description — currently basic |
| video_url | TEXT | `https://youtu.be/{id}` |

### `scores` — Sheet music PDF metadata

| Column | Type | How it's set |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| file_path | TEXT UNIQUE | Absolute path to PDF |
| filename | TEXT | Just the file name |
| composer_dir | TEXT | Parent directory name (`Bach`, `Chopin`, `pdf`, ...) |
| composer | TEXT | Extracted from filename first, then directory fallback |
| catalog_type | TEXT | `BWV` / `Opus` / `K` / `D` / `unknown` |
| catalog_number | TEXT | Extracted catalog number |
| piece_name | TEXT | OCR text from first page if available |
| piece_type | TEXT | `Prelude`, `Sonata`, `Waltz`, etc. — regex on filename |
| arranger | TEXT | Arranger name if detected (`Busoni`, `Liszt`, ...) |
| genre | TEXT | `classical` / `jazz` / `film` / `sacred` / `unknown` — from directory |
| is_compilation | INTEGER | `1` if filename suggests a collection (Complete, Book, Volume...) |
| source | TEXT | Relative path from `~/Documents/Piano/Partitions/` |

## ChromaDB — `~/.local/share/chroma/`

Two collections for vector similarity search. Default embedding model:
`all-MiniLM-L6-v2` (downloaded on first use, ~80MB cache at
`~/.cache/chroma/`).

### `videos` collection (424 entries)

| Field | Content |
|-------|---------|
| id | YouTube video ID |
| document | Video `title` |
| metadata.type | `"video"` |
| metadata.composer | Detected composer |
| metadata.catalog_type | BWV/Opus/etc |
| metadata.catalog_number | Extracted number |
| metadata.classification | tutorial/performance/etc |
| metadata.url | `https://youtu.be/{id}` |

### `scores` collection (458 entries)

| Field | Content |
|-------|---------|
| id | Score DB ID (as string) |
| document | Cleaned filename + composer + catalog + piece type, pipe-separated |
| metadata.type | `"score"` |
| metadata.composer | Composer name |
| metadata.catalog_type | BWV/Opus/etc |
| metadata.catalog_number | Extracted number |
| metadata.file_path | Absolute path to PDF |

### Why both SQLite and ChromaDB?

- **SQLite**: exact lookups, filtering, stats (`WHERE composer = 'Bach'`, `GROUP BY catalog_type`), bulk operations
- **ChromaDB**: fuzzy/semantic search handles typos, different languages,
  partial names (`"prelude a minor"` → BWV 543), and cross-modal matching
  (score text → find related videos)

## Playlists

```
/home/BIG/src/AI/piano-repertoire-index/
  piano.txt      432 IDs   (main piano playlist)
  classical.txt  161 IDs
  AI.txt          61 IDs
```

Each file: one YouTube video ID per line, no headers.

## Scripts

All in `scripts/`. Run from the repo root.

### `fetch_playlist.py`

Fetch video IDs from a YouTube playlist into a `.txt` file.

```
Usage: fetch_playlist.py [--update] <playlist_id> [output_name]

Examples:
  fetch_playlist.py PL_abc123_de new_playlist
      → Full fetch, writes all IDs to new_playlist.txt

  fetch_playlist.py --update piano PL_abc123_de
      → Appends only new IDs to existing piano.txt
      → Skips IDs already in the file
      → Prints count of new vs total

Options:
  --update    Only append IDs not already in the output file
```

### `index_videos.py`

Fetch metadata from YouTube Data API, classify, extract catalog info,
write to SQLite, and update ChromaDB.

```
Usage: index_videos.py [--all | --rebuild | file.txt ...]

Examples:
  index_videos.py piano.txt
      → Fetch metadata for new IDs in piano.txt
      → Skip already-indexed videos
      → Incremental Chroma update (only new entries)

  index_videos.py --all
      → Scan all .txt files in the repo root
      → Same incremental logic per file

  index_videos.py --rebuild
      → No API calls
      → Wipe and rebuild Chroma from existing SQLite data
      → Use after modifying classifications or adding metadata

Flags:
  --all       Process all .txt files in the repo root
  --rebuild   Rebuild ChromaDB from scratch (no API calls)

How it works:
  1. Reads video IDs from the input file(s)
  2. Compares against existing `videos` table by primary key
  3. API call (batch of 50) only for IDs not yet in DB
  4. Per video: classifies (tutorial/performance/gear/other),
     extracts catalog numbers (BWV/Opus/K) and composer
  5. Writes to SQLite
  6. ChromaDB: incremental add for new videos, or full rebuild with --rebuild
```

### `index_scores.py`

Scan the sheet music directory, extract metadata, run OCR on scanned
PDFs, write to SQLite and ChromaDB.

```
Usage: index_scores.py [--quick | --ocr]

Examples:
  index_scores.py
      → Full re-index: scan all PDFs, run OCR on classical scores
      → Wipes and rebuilds scores table + Chroma collection

  index_scores.py --quick
      → Filename-based extraction only
      → No OCR (much faster)
      → Use after adding many new files to get a quick baseline

Flags:
  --quick   Skip OCR pass (filename extraction only)
  --ocr     Only run OCR on unknown-catalog classical scores

How it works:
  1. Walks ~/Documents/Piano/Partitions/ recursively
  2. Extracts composer from filename regex, then directory name
  3. Extracts catalog numbers from filenames (BWV, Opus, K, D)
  4. Detects piece type, arranger, genre, compilation flag
  5. OCR pass: for scores with known composer but unknown catalog,
     extracts first page as image → Tesseract → searches for catalog
     numbers in OCR output
  6. Writes to SQLite
  7. Builds Chroma collection with rich document text
     (cleaned filename | composer | piece_name | catalog | piece_type)
```

### `match.py`

Cross-modal vector search across videos and scores.

```
Usage: match.py [query | flags]

Examples:
  match.py "Prelude and Fugue A minor BWV 543"
      → Searches both videos and scores, shows results

  match.py --score "Chopin Waltz Op 69"
      → Uses score text to find matching videos

  match.py --video "https://youtu.be/KQXxS5nDvdI"
      → Uses video title to find matching scores

  match.py --browse
      → Interactive mode: enter queries, 'q' to quit

Flags:
  --score    Treat query as score text, search videos
  --video    Treat query as video URL/ID, search scores
  --browse   Interactive REPL mode
```

## Classification Logic

Applied by `index_videos.py` to each video. Priority order:

```
1. Syllabus exam (ABRSM, RCM)         → tutorial
2. Tutorial keywords                   → tutorial
   (lesson, learn, practice, technique, masterclass,
    cours, exercice, memoriser, how to play, ...)
3. Gear keywords                       → gear
   (review, keyboard, digital piano, headphones,
    comparison, unboxing, ...)
4. Performance keywords (and no tutorial) → performance
   (plays, performs, recital, concert, pianist,
    recording, live, ...)
5. No match                            → other
```

## Catalog Regex Patterns

Applied to video titles + first 500 chars of description, and score
filenames (with underscores/hyphens normalized to spaces).

| Catalog | Regex pattern |
|---------|--------------|
| BWV | `BWV\s*(\d+[a-zA-Z]?(?:/\d+)?)` — catches `BWV 846`, `BWV 1001/1`, `BWV 846a` |
| K/KV | `\b(K\.|KV|Köchel|Koechel)\s*(\d+)` |
| D | `\bD\.\s*(\d+)` |
| Opus | `(?:Op\.|Opus|op\.|OP\.)\s*(\d+)` or `op\s*(\d+)` or `op(\d{1,3})` |
| Opus No. | Same as Opus + optional `(?:No\.|no\.|n[oô]\.?|nr\.?)?\s*(\d+)?` |

## Workflows

### Adding a new playlist

```bash
cd /home/BIG/src/AI/piano-repertoire-index
./scripts/fetch_playlist.py PL_xyz_new_playlist new_name
./scripts/index_videos.py new_name.txt
```

### Updating an existing playlist

```bash
# 1. Fetch only new videos added since last fetch
./scripts/fetch_playlist.py --update piano PLJtnYnh4N0cvN-201yozJGjgZaZ2gGal4
./scripts/fetch_playlist.py --update classical PLJtnYnh4N0cstdeQs2rYedL7C9D1v9qd7
./scripts/fetch_playlist.py --update AI PLJtnYnh4N0ctG-mxLIBXd-Q--qTjyUAJR

# 2. Index new videos (incremental SQLite + Chroma update)
./scripts/index_videos.py piano.txt classical.txt AI.txt

# 3. Clean dead IDs (deleted/private videos return no metadata)
python3 - << 'EOF'
import os, sqlite3
conn = sqlite3.connect(os.path.expanduser("~/.local/share/piano-repertoire-index/piano.db"))
in_db = set(r[0] for r in conn.execute("SELECT id FROM videos").fetchall())
conn.close()
for name in ["piano", "classical", "AI"]:
    path = f"/home/BIG/src/AI/piano-repertoire-index/{name}.txt"
    with open(path) as f:
        ids = [l.strip() for l in f if l.strip()]
    kept = [v for v in ids if v in in_db]
    with open(path, "w") as f:
        f.write("\n".join(kept))
    print(f"{name}.txt: {len(ids)} -> {len(kept)}")
EOF
```

### Playlist IDs

| Playlist | ID |
|----------|----|
| piano | `PLJtnYnh4N0cvN-201yozJGjgZaZ2gGal4` |
| classical | `PLJtnYnh4N0cstdeQs2rYedL7C9D1v9qd7` |
| AI | `PLJtnYnh4N0ctG-mxLIBXd-Q--qTjyUAJR` |

### Token refresh (invalid_grant / auth errors)

The Google OAuth refresh token occasionally goes stale (error:
`invalid_grant: Bad Request`). When the API returns
`Request had invalid authentication credentials`, run:

```bash
./scripts/refresh_token.py
```

This starts a local server on port 5678 and prints an auth URL. Open
it in your browser, approve the scopes, and the script saves the new
token to `~/.hermes/google_token.json`. Then retry the update.

Note: port 5678 must be free (the registered redirect URI is
`http://localhost:5678/rest/oauth2-credential/callback`).

### Adding new sheet music

```bash
# Copy PDFs into ~/Documents/Piano/Partitions/ComposerName/
./scripts/index_scores.py --quick    # Fast scan
./scripts/index_scores.py            # Full with OCR
```

### Searching

```bash
./scripts/match.py "Bach BWV 846"
./scripts/match.py --score "Schumann Traumerei"
./scripts/match.py --browse
```

### Rebuilding after changing classification rules

```bash
./scripts/index_videos.py --rebuild        # Re-embed existing data
./scripts/index_scores.py                  # Full re-index scores
```

## OAuth & API Setup

- **Project**: `certain-root-484705-k6` (Google Cloud)
- **API**: YouTube Data API v3
- **OAuth client**: Web application type
- **Scopes**: `youtube.readonly` + calendar, drive, gmail, docs, sheets
- **Token file**: `~/.hermes/google_token.json`
- **Client secret**: `~/.hermes/google_client_secret.json`
- **Redirect URI**: `http://localhost:5678/rest/oauth2-credential/callback`
- **Refresh**: Token auto-refreshes via `google-auth-oauthlib`
- **Rate limit**: 0.3s delay between API batches

## Current Stats

| | Videos | Scores |
|---|---|---|
| Total | 424 | 458 |
| With catalog | 123 (84 BWV + 35 Opus + 4 K) | 52 (18 BWV + 31 Opus + 3 D) |
| Tutorial | 334 | — |
| Performance | 29 | — |
| Gear | 16 | — |
| Other | 45 | — |

## File Layout

```
/home/BIG/src/AI/piano-repertoire-index/
  piano.txt              Video IDs (piano playlist)
  classical.txt          Video IDs
  AI.txt                 Video IDs
  README.md              This file
  scripts/
    fetch_playlist.py    Download IDs from YouTube
    index_videos.py      Metadata → SQLite + Chroma
    index_scores.py      Scores → SQLite + Chroma
    match.py             Cross-modal search

~/.local/share/piano-repertoire-index/
  piano.db               SQLite database

~/.local/share/chroma/   ChromaDB persistent storage
  chroma.sqlite3         Vector index data

~/Documents/Piano/Partitions/    458 PDFs
  J.S. Bach/           41 files
  Chopin/              12 files
  Schumann/            10 files
  ... (30+ dirs)
  pdf/                 257 files (popular songs)
  Jazz/                28 files

~/.hermes/
  google_token.json           OAuth token (youtube.readonly)
  google_client_secret.json   OAuth client credentials

~/.cache/chroma/onnx_models/  Embedding model cache (~80MB)
```
