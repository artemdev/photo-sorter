#!/usr/bin/env python3
"""Compute a SHA-256 hash for every image and video in <root>/draft/.

Videos sharing an image's name are hashed too: the mover only decides from their
recording date whether they're that photo's Live Photo clip or a separate video.

Results go to <root>/.photo-db/draft-hashes.tsv (sha256, size, mtime_ns, name).
Files whose size and modification time are unchanged since the last run are
not re-hashed. Read-only on the photos themselves.

--rebuild-db instead re-hashes every image and standalone video under <root>/media/ and rewrites
<root>/.photo-db/pictures.tsv, the library index move_from_draft.py checks against.
Use it if media/ was changed by hand.

Usage: hash_draft.py <drive-root> [--rebuild-db]
"""
import argparse
import datetime
import hashlib
import os
import re
import sys

IMAGE_EXTS = {
    "jpg", "jpeg", "heic", "heif", "png", "gif", "tif", "tiff", "webp", "bmp",
    "dng", "cr2", "cr3", "nef", "arw", "raf", "orf", "rw2", "srw", "pef",
}
VIDEO_EXTS = {"mov", "mp4", "m4v", "3gp", "avi", "mkv", "mts", "m2ts", "wmv", "webm"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
DRAFT_HEADER = "sha256\tsize\tmtime_ns\tname\n"
DB_HEADER = "sha256\tsize\tpath\tdate\tdate_source\tcity\tadded\n"


def is_image(name):
    return not name.startswith(".") and name.rpartition(".")[2].lower() in IMAGE_EXTS


def media_files(names):
    """Images, plus videos that have no same-named image (those are Live Photo companions)."""
    names = [n for n in names if not n.startswith(".")]
    image_stems = {n.rpartition(".")[0].lower() for n in names if is_image(n)}
    return [n for n in names if is_image(n)
            or (n.rpartition(".")[2].lower() in VIDEO_EXTS and n.rpartition(".")[0].lower() not in image_stems)]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_tsv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    return [l.split("\t") for l in lines[1:] if l]


def progress(i, total):
    if i % 500 == 0 or i == total:
        print(f"  hashed {i}/{total}", flush=True)


def hash_draft(root, db_dir):
    draft = os.path.join(root, "draft")
    if not os.path.isdir(draft):
        sys.exit("No draft/ folder yet - run import_to_draft.py first.")
    out = os.path.join(db_dir, "draft-hashes.tsv")
    cache = {r[3]: r for r in read_tsv(out)}

    names = sorted(n for n in (e.name for e in os.scandir(draft) if e.is_file())
                   if is_image(n) or (not n.startswith(".") and n.rpartition(".")[2].lower() in VIDEO_EXTS))
    rows, todo = [], []
    for name in names:
        st = os.stat(os.path.join(draft, name))
        old = cache.get(name)
        if old and old[1] == str(st.st_size) and old[2] == str(st.st_mtime_ns):
            rows.append(old)
        else:
            todo.append((name, st))
    # Save each hash as soon as it's computed, so an interrupted run resumes where it stopped.
    with open(out, "w", encoding="utf-8") as f:
        f.write(DRAFT_HEADER)
        f.writelines("\t".join(r) + "\n" for r in rows)
        for i, (name, st) in enumerate(todo, 1):
            row = [sha256(os.path.join(draft, name)), str(st.st_size), str(st.st_mtime_ns), name]
            rows.append(row)
            f.write("\t".join(row) + "\n")
            f.flush()
            progress(i, len(todo))
    rows.sort(key=lambda r: r[3])
    fresh = len(todo)
    with open(out, "w", encoding="utf-8") as f:
        f.write(DRAFT_HEADER)
        f.writelines("\t".join(r) + "\n" for r in rows)

    library = {r[0]: r[2] for r in read_tsv(os.path.join(db_dir, "pictures.tsv"))}
    seen, in_library, in_batch = set(), 0, 0
    for r in rows:
        if r[0] in library:
            in_library += 1
        elif r[0] in seen:
            in_batch += 1
        seen.add(r[0])
    print(f"Hashed {len(rows)} images/videos in draft/ ({fresh} new, {len(rows) - fresh} unchanged since last run).")
    print(f"  {in_library} already exist in media/ (will go to duplicates/)")
    print(f"  {in_batch} are copies of another file in this draft batch (will go to duplicates/)")
    print(f"  {len(rows) - in_library - in_batch} are new (will go to media/)")
    print(f"Saved to {out}")


def rebuild_db(root, db_dir):
    media = os.path.join(root, "media")
    if not os.path.isdir(media):
        sys.exit("No media/ folder yet - nothing to index.")
    old = {r[2]: r for r in read_tsv(os.path.join(db_dir, "pictures.tsv"))}
    paths = []
    for dirpath, dirnames, filenames in os.walk(media):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        paths += [os.path.join(dirpath, n) for n in media_files(filenames)]
    paths.sort()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    rows = []
    for i, p in enumerate(paths, 1):
        rel = os.path.relpath(p, root)
        prev = old.get(rel)
        if prev:  # keep the date/city the mover recorded, refresh hash and size
            rows.append([sha256(p), str(os.path.getsize(p))] + prev[2:])
        else:
            m = re.match(r"media/(\d{4})/([^/]+)/", rel)
            month = m and (m.group(2) if re.fullmatch(r"\d{2}", m.group(2))
                           else f"{MONTHS.index(m.group(2)) + 1:02}" if m.group(2) in MONTHS else None)
            date = f"{m.group(1)}-{month}" if month else (m.group(1) if m else "")
            rows.append([sha256(p), str(os.path.getsize(p)), rel, date, "folder", "", now])
        progress(i, len(paths))
    with open(os.path.join(db_dir, "pictures.tsv"), "w", encoding="utf-8") as f:
        f.write(DB_HEADER)
        f.writelines("\t".join(r) + "\n" for r in rows)
    added = sum(1 for r in rows if r[2] not in old)
    print(f"Rebuilt library index: {len(rows)} images/videos in media/ ({added} were missing from the old index).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--rebuild-db", action="store_true")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    db_dir = os.path.join(root, ".photo-db")
    os.makedirs(db_dir, exist_ok=True)
    rebuild_db(root, db_dir) if args.rebuild_db else hash_draft(root, db_dir)


if __name__ == "__main__":
    main()
