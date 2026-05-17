#!/usr/bin/env python3
"""Fetch videos from a YouTube playlist and save IDs to a file.

Usage:
  fetch_playlist.py <playlist_id> [output_name]     # Full fetch
  fetch_playlist.py --update <playlist_id> [name]   # Only new videos since last fetch
"""
import json, requests, time, os, sys

TOKEN_PATH = os.path.expanduser("~/.hermes/google_token.json")
OUT_DIR = "/home/BIG/src/DATA/YT"

update_mode = "--update" in sys.argv
args = [a for a in sys.argv[1:] if not a.startswith("--")]

if len(args) < 1:
    print("Usage: fetch_playlist.py [--update] <playlist_id> [output_name]")
    sys.exit(1)

pl_id = args[0]
out_name = args[1] if len(args) > 1 else pl_id
path = f"{OUT_DIR}/{out_name}.txt"

# Load existing IDs if updating
existing = set()
if update_mode and os.path.exists(path):
    with open(path) as f:
        existing = set(line.strip() for line in f if line.strip())
    print(f"Existing: {len(existing)} videos in {out_name}.txt")

with open(TOKEN_PATH) as f:
    tk = json.load(f)

headers = {"Authorization": f"Bearer {tk['token']}"}
new_ids = []
page = None

while True:
    params = {"part": "snippet", "playlistId": pl_id, "maxResults": 50}
    if page:
        params["pageToken"] = page
    r = requests.get("https://www.googleapis.com/youtube/v3/playlistItems", params=params, headers=headers)
    data = r.json()
    if "error" in data:
        print(f"Error: {data['error']['message']}")
        sys.exit(1)
    for item in data.get("items", []):
        vid = item["snippet"]["resourceId"]["videoId"]
        if update_mode:
            if vid not in existing:
                new_ids.append(vid)
        else:
            new_ids.append(vid)
    page = data.get("nextPageToken")
    if not page:
        break
    time.sleep(0.3)

if update_mode:
    all_ids = list(existing) + new_ids
    with open(path, "w") as f:
        f.write("\n".join(all_ids))
    print(f"{len(new_ids)} new videos appended. Total: {len(all_ids)} → {path}")
else:
    with open(path, "w") as f:
        f.write("\n".join(new_ids))
    print(f"{len(new_ids)} videos → {path}")
