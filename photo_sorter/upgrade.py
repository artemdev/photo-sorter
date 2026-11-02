#!/usr/bin/env python3
"""Bring a library made by an older version of these scripts up to the current layout:

  pictures/          -> media/                 (the library folder's old name)
  media/YYYY/MM/     -> media/YYYY/<Month>/    (07 -> July)

Updates the paths in .photo-db/pictures.tsv and .photo-db/duplicates.tsv so duplicate
checks keep working, and logs every folder rename to .photo-db/moves.log so it can be
undone. Stops without changing anything if both the old and new folder exist
(pictures/ and media/, or 07 and July).

Usage: photo-sorter upgrade <drive> [--dry-run]
"""
import argparse
import datetime
import os
import re
import sys

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
TABLES = {"pictures.tsv": [2], "duplicates.tsv": [2]}  # column indexes holding library paths


def read_lines(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read().splitlines()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    db_dir = os.path.join(root, ".photo-db")
    old_lib, lib = os.path.join(root, "pictures"), os.path.join(root, "media")

    renames, conflicts = [], []  # (old relative folder, new relative folder), applied in order
    if os.path.isdir(old_lib):
        (conflicts if os.path.exists(lib) else renames).append(("pictures", "media"))
    current = old_lib if renames else lib  # where the month folders are right now
    if os.path.isdir(current):
        for year in sorted(os.listdir(current)):
            ydir = os.path.join(current, year)
            if not re.fullmatch(r"\d{4}", year) or not os.path.isdir(ydir):
                continue
            for mm in sorted(os.listdir(ydir)):
                if re.fullmatch(r"0[1-9]|1[0-2]", mm) and os.path.isdir(os.path.join(ydir, mm)):
                    pair = (f"media/{year}/{mm}", f"media/{year}/{MONTHS[int(mm) - 1]}")
                    if os.path.exists(os.path.join(ydir, MONTHS[int(mm) - 1])):
                        conflicts.append(pair)
                    else:
                        renames.append(pair)
    if conflicts:
        sys.exit("Stopped, nothing renamed: both folders exist for "
                 + ", ".join(f"{a}/ and {b}/" for a, b in conflicts))
    if not renames:
        print("Nothing to upgrade - the library is already media/YYYY/<Month>/.")
        return

    def fix(path):
        for old, new in renames:
            if path.startswith(old + "/"):
                path = new + path[len(old):]
        return path

    updated = {}
    for table, cols in TABLES.items():
        lines = read_lines(os.path.join(db_dir, table))
        if lines is None:
            continue
        out, changed = [lines[0]], 0
        for line in lines[1:]:
            cells = line.split("\t")
            for c in cols:
                if c < len(cells) and fix(cells[c]) != cells[c]:
                    cells[c] = fix(cells[c])
                    changed += 1
            out.append("\t".join(cells))
        updated[table] = (out, changed)

    if not args.dry_run:
        now = datetime.datetime.now().isoformat(timespec="seconds")
        with open(os.path.join(db_dir, "moves.log"), "a", encoding="utf-8") as log:
            for old, new in renames:
                parent, old_name = os.path.split(os.path.join(root, old))
                new_name = os.path.basename(new)
                os.rename(os.path.join(parent, old_name), os.path.join(parent, new_name))
                # On exFAT, macOS keeps folder metadata in a "._07" sidecar; rename it too.
                side = os.path.join(parent, "._" + old_name)
                if os.path.exists(side) and not os.path.exists(os.path.join(parent, "._" + new_name)):
                    os.rename(side, os.path.join(parent, "._" + new_name))
                log.write(f"{now}\trename\t{old}/\t{new}/\n")
        for table, (out, _) in updated.items():
            with open(os.path.join(db_dir, table), "w", encoding="utf-8") as f:
                f.write("\n".join(out) + "\n")

    print(("DRY RUN (nothing renamed)" if args.dry_run else "Done") + f": {len(renames)} folders, e.g. "
          + ", ".join(f"{a}/ -> {b}/" for a, b in renames[:3]))
    for table, (_, changed) in updated.items():
        print(f"  {table}: {changed} paths {'to update' if args.dry_run else 'updated'}")


if __name__ == "__main__":
    main()
