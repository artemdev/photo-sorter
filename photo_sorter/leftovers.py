#!/usr/bin/env python3
"""Move lone .AAE edit files from the drive root into <root>/leftovers/.

A lone .AAE is an iPhone edit file whose photo or video is not on the root
(same base name, any case). On its own it can't be opened or applied, so it
only clutters the root. Nothing is deleted; only moved. Each move is logged
to <root>/.photo-db/moves.log so it can be undone.

Usage: photo-sorter leftovers <drive> [--dry-run]
"""
import argparse
import datetime
import os
import sys

from .importer import IMAGE_EXTS, VIDEO_EXTS, split


def free_name(name, dest_dir):
    """Return name, or name with a -2/-3 suffix, so it doesn't clash in dest_dir."""
    stem, dot, ext = name.rpartition(".")
    candidate, n = name, 1
    while os.path.exists(os.path.join(dest_dir, candidate)):
        n += 1
        candidate = f"{stem}-{n}{dot}{ext}"
    return candidate


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        sys.exit(f"Not a folder: {root}")
    leftovers = os.path.join(root, "leftovers")
    db_dir = os.path.join(root, ".photo-db")

    groups = {}  # lower-case stem -> set of extensions on root
    aae_files = []
    for entry in os.scandir(root):
        if entry.name.startswith(".") or not entry.is_file(follow_symlinks=False):
            continue
        stem, ext = split(entry.name)
        groups.setdefault(stem.lower(), set()).add(ext)
        if ext == "aae":
            aae_files.append(entry.name)

    lone = sorted(m for m in aae_files
                  if not groups[split(m)[0].lower()] & (IMAGE_EXTS | VIDEO_EXTS))

    if not args.dry_run and lone:
        os.makedirs(leftovers, exist_ok=True)
        os.makedirs(db_dir, exist_ok=True)
        now = datetime.datetime.now().isoformat(timespec="seconds")
        with open(os.path.join(db_dir, "moves.log"), "a", encoding="utf-8") as log:
            for m in lone:
                dest_name = free_name(m, leftovers)
                os.rename(os.path.join(root, m), os.path.join(leftovers, dest_name))
                # On exFAT, macOS keeps metadata in "._name" sidecars; take it along if the OS left it.
                side_src = os.path.join(root, "._" + m)
                side_dst = os.path.join(leftovers, "._" + dest_name)
                if os.path.exists(side_src) and not os.path.exists(side_dst):
                    os.rename(side_src, side_dst)
                log.write(f"{now}\tleftovers\t{m}\tleftovers/{dest_name}\n")

    mode = "DRY RUN (nothing moved)" if args.dry_run else "Done"
    print(f"{mode}: {len(lone)} lone .AAE edit files -> leftovers/")
    kept = len(aae_files) - len(lone)
    if kept:
        print(f"{kept} .AAE files kept on root because their photo or video is still there "
              "(run the import step first)")


if __name__ == "__main__":
    main()
