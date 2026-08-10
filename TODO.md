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

---

## Done

- [x] Playlist updates (3 playlists, 662 videos in DB, dead IDs cleaned)
- [x] OAuth token refresh script (`scripts/refresh_token.py`) + docs
- [x] Row_factory fixes in index_videos.py / index_scores.py
- [x] Clair de Lune score added (Suite bergamasque, Henle)
- [x] Seasons/Tchaikovsky score cataloged as Op. 37a
- [x] GitHub repo created: `ageneau/piano-repertoire-index`
- [x] Skill saved: `piano-video-score-index`
