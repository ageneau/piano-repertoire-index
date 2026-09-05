# AGENTS.md

Guidance for AI agents working in this repository.

## What this is

Index of piano repertoire: YouTube videos (playlists) and local sheet music
scores, with metadata extraction (composer, catalog numbers) and
cross-modal matching. The heavy data lives OUTSIDE this repo:

- SQLite DB: `/home/BIG/src/DATA/YT/piano.db` (not fully in git — only
  committed occasionally as a snapshot)
- ChromaDB vectors: `~/.local/share/chroma/` (user home = `/home/sylvain`,
  NOT in git)
- Scores: `~/Documents/Piano/Partitions/` (~463 PDFs, composer dirs)
- Video ID files: `piano.txt`, `classical.txt`, `AI.txt` (in git)

## Layout

```
/home/BIG/src/DATA/YT/
  piano.db          SQLite: videos + scores tables
  piano.txt         video IDs from "piano" YouTube playlist
  classical.txt     video IDs from "classical" playlist
  AI.txt            video IDs from "AI" playlist
  README.md         full docs (schema, workflows)
  TODO.md           open items
  scripts/
    fetch_playlist.py    pull video IDs from YouTube (--update = incremental)
    index_videos.py      metadata -> SQLite + ChromaDB
    index_scores.py      scan score dirs -> SQLite + ChromaDB (+OCR w/o --quick)
    match.py             cross-modal vector search
    refresh_token.py     re-auth Google OAuth when token goes stale
```

## Key facts

- **Path split**: repo root is `/home/BIG/src/DATA/YT` but `~` = `/home/sylvain`.
  Use absolute paths in scripts; do not assume `~` == repo-adjacent.
- **Google OAuth**: token `~/.hermes/google_token.json`, client secret
  `~/.hermes/google_client_secret.json`. Redirect URI:
  `http://localhost:5678/rest/oauth2-credential/callback` — port 5678 must
  be free for re-auth.
- **Access token goes stale frequently** (even when file says unexpired).
  If API returns "invalid authentication credentials", refresh the token
  with google-auth first (`creds.refresh(Request())`); if that raises
  `invalid_grant`, run `scripts/refresh_token.py` and have the user click
  through the browser.
- **ChromaDB**: `index_scores.py`/`index_videos.py` rebuild their whole
  collection each run. `conn.row_factory = sqlite3.Row` MUST be set before
  the Chroma section (scripts select rows by name there).
- **OCR**: tesseract + pymupdf; noisy on sheet music. OCR pass only when
  no `--quick`. Runs slow (minutes).
- **Playlist IDs** (used by fetch_playlist.py --update):
  piano `PLJtnYnh4N0cvN-201yozJGjgZaZ2gGal4`,
  classical `PLJtnYnh4N0cstdeQs2rYedL7C9D1v9qd7`,
  AI `PLJtnYnh4N0ctG-mxLIBXd-Q--qTjyUAJR`.

## Workflows

### Update all playlists (recurring task)

```bash
cd /home/BIG/src/DATA/YT
python3 scripts/fetch_playlist.py --update piano PLJtnYnh4N0cvN-201yozJGjgZaZ2gGal4
python3 scripts/fetch_playlist.py --update classical PLJtnYnh4N0cstdeQs2rYedL7C9D1v9qd7
python3 scripts/fetch_playlist.py --update AI PLJtnYnh4N0ctG-mxLIBXd-Q--qTjyUAJR
python3 scripts/index_videos.py piano.txt classical.txt AI.txt
```

Dead video IDs (deleted/private — API returns no metadata) should be
removed from the .txt files after indexing; they never match DB rows.

### Add a score

Copy the PDF into `~/Documents/Piano/Partitions/<Composer>/`, then:

```bash
python3 scripts/index_scores.py --quick
```

Filename catalog patterns (BWV/Opus/K/D) are extracted automatically;
regex misses some variants (`K466`, `MazurkasOp7`) — fix with a manual
`UPDATE scores SET catalog_type=..., catalog_number=...` when needed.

## Environment

- Python via `uv` (system installs: `uv pip install --system <pkg>`)
- No venv. Scripts run with plain `python3`.
- Google API access via `requests` + OAuth token file.
- Do not print or commit tokens/keys.

## Git

- Repo on GitHub: `git@github.com:ageneau/piano-repertoire-index.git`
- `.gitignore` excludes pre-existing channel dirs (`@*`), subscription
  exports, playlist .txt churn is committed.
- `piano.db` is a committed snapshot; refresh/commit occasionally but it
  changes on every index run.
