# TODO

Open items for the piano repertoire index.

## 1. Expand compilation scores into individual pieces
WTC BWV 846-869 (24 preludes/fugues), Chopin Op. 69 (2 waltzes), Op. 116,
Suite bergamasque (4 movements), etc. → one row per piece so each matches
videos cleanly. Use a `score_pieces` table (1 score → N pieces) or expand
catalog ranges.

## 2. Add playlist-name column / junction table
Track which YouTube playlist each video came from. Video can be in multiple
playlists → junction table (`video_id`, `playlist_id`, `playlist_name`).
Needs `index_videos.py` to record the source file per batch.

## 3. Add choir music playlist
Classical playlist has almost no choir content (only Netherlands Bach
Society chorale + a Choir of New College album). Find and add a choir
playlist.

## 4. Fill Chopin Barcarolle Op. 60 gap
No Barcarolle score (Chopin Op. 60) and no video in DB. Find video on
YouTube, download score from IMSLP.

## 5. Write Paul Barton performance playlist
13 Paul Barton performances identified in DB (Bach, Chopin, Handel,
Couperin). Write video IDs to `paul_barton.txt` so they can be turned
into a YouTube playlist.

## 6. Find more Bach guitar performances
Only 2 in DB (Segovia Gavotte from Lute Suite, Feuillâtre BWV 639).
Find and add more to the classical playlist.

## 7. ModernBERT reranker for cross-modal search
`match.py` leans on ChromaDB's *default* embedding function and nothing else —
`all-MiniLM-L6-v2`, 384-dim, no explicit model anywhere in the script. Two
stages, cheapest first:

1. **Drop-in embedding swap, no training.** Re-index both collections with a
   ModernBERT embedding model — `nomic-ai/modernbert-embed-base` or
   `lightonai/modernbert-embed-large` (149M/395M params, 8192 context, Apache
   2.0). At the current 688 videos + 465 scores (DB and both collections agree),
   re-embedding is seconds of CPU. Queries must then be embedded with the same
   model, which means passing an explicit embedding function to match.py instead
   of accepting the default, plus a re-index of both collections.
2. **Actual reranking.** Retrieve top-50 with the bi-encoder, then rerank with a
   ModernBERT cross-encoder — or `lightonai/LateOn`, a ModernBERT late-interaction
   model — down to top 5. Note ModernBERT is not itself a reranker, it is a
   backbone you fine-tune into one; the training pairs are free here, because the
   DB's own catalog columns give query→correct-row pairs (a search for "BWV 846"
   must retrieve the rows tagged BWV 846).

Build the eval set and record the baseline first: ~30-50 cases of
query→expected row pulled from the catalog columns, scored on recall@5 and
recall@10, measured before and after. An unmeasured reranker can demote relevant
rows out of the window and still look plausible.

Why it is worth doing: retrieval quality *is* this project's product, and the
two-stage retrieve-then-rerank pattern is the standard way to buy it. No API key,
no GPU, nothing leaves the box.

---

## Done

- [x] Playlist updates (3 playlists, 662 videos in DB, dead IDs cleaned)
- [x] OAuth token refresh script (`scripts/refresh_token.py`) + docs
- [x] Row_factory fixes in index_videos.py / index_scores.py
- [x] Clair de Lune score added (Suite bergamasque, Henle)
- [x] Seasons/Tchaikovsky score cataloged as Op. 37a
- [x] GitHub repo created: `ageneau/piano-repertoire-index`
- [x] Skill saved: `piano-video-score-index`
