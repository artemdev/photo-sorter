#!/usr/bin/env python3
"""Move every image and video lying loose on the drive root into <root>/draft/.

Live Photo / edit companions (.MOV, .AAE) that share an image's base name
travel with it; an .AAE sharing a standalone video's name travels with the
video. Nothing is deleted; only moved. Each move is logged to
<root>/.photo-db/moves.log so it can be undone.

Usage: photo-sorter import <drive> [--dry-run]
"""
import argparse
import datetime
import os
import sys

IMAGE_EXTS = {
    "jpg", "jpeg", "heic", "heif", "png", "gif", "tif", "tiff", "webp", "bmp",
    "dng", "cr2", "cr3", "nef", "arw", "raf", "orf", "rw2", "srw", "pef",
}
VIDEO_EXTS = {"mov", "mp4", "m4v", "3gp", "avi", "mkv", "mts", "m2ts", "wmv", "webm"}
COMPANION_EXTS = {"mov", "aae"}
MANAGED_DIRS = ("draft", "media", "duplicates", "leftovers")


def split(name):
    stem, dot, ext = name.rpartition(".")
    return (stem, ext.lower()) if dot else (name, "")


def free_stem(stem, members, dest_dir):
    """Return a stem under which every member of the group fits in dest_dir."""
    candidate, n = stem, 1
    while any(os.path.exists(os.path.join(dest_dir, candidate + "." + m.rpartition(".")[2]))
              for m in members):
        n += 1
        candidate = f"{stem}-{n}"
    return candidate


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        sys.exit(f"Not a folder: {root}")
    draft = os.path.join(root, "draft")
    db_dir = os.path.join(root, ".photo-db")

    groups = {}  # lower-case stem -> list of file names
    for entry in os.scandir(root):
        if entry.name.startswith(".") or not entry.is_file(follow_symlinks=False):
            continue
        groups.setdefault(split(entry.name)[0].lower(), []).append(entry.name)

    to_move, left = [], {}
    for members in groups.values():
        exts = {split(m)[1] for m in members}
        if exts & IMAGE_EXTS:
            moving = [m for m in members if split(m)[1] in IMAGE_EXTS | COMPANION_EXTS]
        elif exts & VIDEO_EXTS:
            moving = [m for m in members if split(m)[1] in VIDEO_EXTS | {"aae"}]
        else:
            moving = []
        if moving:
            to_move.append(sorted(moving))
            members = [m for m in members if m not in moving]
        for m in members:
            ext = split(m)[1] or "(no extension)"
            left[ext] = left.get(ext, 0) + 1

    n_images = sum(1 for g in to_move for m in g if split(m)[1] in IMAGE_EXTS)
    n_videos = sum(1 for g in to_move if not {split(m)[1] for m in g} & IMAGE_EXTS
                   for m in g if split(m)[1] in VIDEO_EXTS)
    n_companions = sum(len(g) for g in to_move) - n_images - n_videos
    renamed = 0

    if not args.dry_run:
        os.makedirs(draft, exist_ok=True)
        os.makedirs(db_dir, exist_ok=True)
        log = open(os.path.join(db_dir, "moves.log"), "a", encoding="utf-8")
        now = datetime.datetime.now().isoformat(timespec="seconds")
    for members in to_move:
        stem = split(members[0])[0]
        new_stem = free_stem(stem, members, draft)
        if new_stem != stem:
            renamed += 1
        if args.dry_run:
            continue
        for m in members:
            dest_name = new_stem + "." + m.rpartition(".")[2]
            src, dst = os.path.join(root, m), os.path.join(draft, dest_name)
            os.rename(src, dst)
            # On exFAT, macOS keeps metadata in "._name" sidecars; take it along if the OS left it.
            side_src, side_dst = os.path.join(root, "._" + m), os.path.join(draft, "._" + dest_name)
            if os.path.exists(side_src) and not os.path.exists(side_dst):
                os.rename(side_src, side_dst)
            log.write(f"{now}\timporter\t{m}\tdraft/{dest_name}\n")
    if not args.dry_run:
        log.close()

    mode = "DRY RUN (nothing moved)" if args.dry_run else "Done"
    print(f"{mode}: {n_images} images + {n_videos} videos + {n_companions} companion files (.MOV/.AAE) -> draft/")
    if renamed:
        print(f"{renamed} groups {'would get' if args.dry_run else 'got'} a -2/-3 suffix because the name was already taken in draft/")
    if left:
        print("Left on root (not photos or videos, e.g. documents or lone .AAE edit files):")
        for ext, n in sorted(left.items(), key=lambda kv: -kv[1]):
            print(f"  {n:>6} .{ext}")
    else:
        print("Nothing else left on root.")
    others = [e.name for e in os.scandir(root) if e.is_dir() and not e.name.startswith(".")
              and e.name not in MANAGED_DIRS]
    if others:
        print("Untouched folders on root: " + ", ".join(sorted(others)))


if __name__ == "__main__":
    main()
