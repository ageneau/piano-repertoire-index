#!/usr/bin/env python3
"""Cross-modal search: find videos matching a score, or scores matching a video.

Usage:
  ./match.py "Bach Prelude in C major BWV 846"   # Free text query
  ./match.py --score "Chopin Waltz Op 69"         # Search videos with score text
  ./match.py --video "https://youtu.be/..."      # Search scores with video title
  ./match.py --browse                             # Interactive mode
"""
import sqlite3, os, sys, re
import chromadb
from chromadb.config import Settings

DB_PATH = os.path.expanduser("~/.local/share/piano-repertoire-index/piano.db")
CHROMA_DIR = os.path.expanduser("~/.local/share/chroma")

client = chromadb.PersistentClient(path=CHROMA_DIR, settings=Settings(anonymized_telemetry=False))
video_col = client.get_collection("videos")
score_col = client.get_collection("scores")
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

def show_video_results(results, label="Results"):
    print(f"\n  {label}:")
    for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
        cls = meta["classification"][:4]
        print(f"  [{dist:.3f}] [{cls}] {doc[:75]}")
        print(f"           {meta.get('url','')}")

def show_score_results(results, label="Results"):
    print(f"\n  {label}:")
    for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
        comp = meta["composer"][:12]
        print(f"  [{dist:.3f}] {comp:12s} | {doc[:80]}")

def search_videos(query, n=8):
    results = video_col.query(query_texts=[query], n_results=n)
    show_video_results(results)

def search_scores(query, n=8):
    results = score_col.query(query_texts=[query], n_results=n)
    show_score_results(results)

def match_score_to_videos(score_text, n=5):
    results = video_col.query(query_texts=[score_text], n_results=n)
    show_video_results(results, "Matching videos")

def match_video_to_scores(video_id_or_url, n=5):
    vid = video_id_or_url.split("/")[-1].split("?")[0].split("&")[0]
    row = conn.execute("SELECT title FROM videos WHERE id=?", (vid,)).fetchone()
    if not row:
        print(f"Video {vid} not found in DB")
        return
    q = row["title"]
    print(f"Query: {q}")
    results = score_col.query(query_texts=[q], n_results=n)
    show_score_results(results, "Matching scores")

if "--browse" in sys.argv:
    # Interactive mode
    print("Enter queries (or 'q' to quit)")
    while True:
        try:
            q = input("\n> ").strip()
        except EOFError: break
        if not q or q == 'q': break
        search_videos(q)
        search_scores(q)
    sys.exit(0)

# Parse args
args = [a for a in sys.argv[1:] if not a.startswith('--')]

if "--score" in sys.argv:
    idx = sys.argv.index("--score")
    q = " ".join(sys.argv[idx+1:]).strip()
    match_score_to_videos(q)
elif "--video" in sys.argv:
    idx = sys.argv.index("--video")
    q = sys.argv[idx+1].strip()
    match_video_to_scores(q)
elif args:
    q = " ".join(args)
    search_videos(q)
    print("\n" + "="*60)
    search_scores(q)
else:
    print(__doc__)
