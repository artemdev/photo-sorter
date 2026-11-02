#!/usr/bin/env python3
"""Move hashed images and videos out of <root>/draft/.

  hash already in the library index (or seen earlier in this batch) -> duplicates/
  otherwise -> media/YYYY/<Month>/<City>/ (or media/YYYY/<Month>/ when there is no GPS),
  e.g. media/2024/July/Oslo/

.MOV/.AAE files sharing an image's base name follow that image. A video with no
same-named image is filed on its own, like a photo (an .AAE edit file with its
name follows it). Nothing is
deleted. Every move is logged to .photo-db/moves.log, every duplicate to
.photo-db/duplicates.tsv, and every new picture is added to .photo-db/pictures.tsv.

Usage: move_from_draft.py <drive-root> [--dry-run]
"""
import argparse
import collections
import datetime
import math
import os
import re
import subprocess
import sys
import tempfile

IMAGE_EXTS = {
    "jpg", "jpeg", "heic", "heif", "png", "gif", "tif", "tiff", "webp", "bmp",
    "dng", "cr2", "cr3", "nef", "arw", "raf", "orf", "rw2", "srw", "pef",
}
VIDEO_EXTS = {"mov", "mp4", "m4v", "3gp", "avi", "mkv", "mts", "m2ts", "wmv", "webm"}
COMPANION_EXTS = {"mov", "aae"}
# Same-named images are processed camera original first (also breaks time ties).
PRIMARY_ORDER = ["heic", "heif", "jpg", "jpeg", "dng", "cr3", "cr2", "nef", "arw", "raf",
                 "orf", "rw2", "srw", "pef", "tif", "tiff", "png", "webp", "gif", "bmp",
                 "mov", "mp4", "m4v", "3gp", "mts", "m2ts", "avi", "mkv", "wmv", "webm"]
DB_HEADER = "sha256\tsize\tpath\tdate\tdate_source\tcity\tadded\n"
DUP_HEADER = "sha256\tduplicate_path\toriginal_path\tdate_found\n"
MAX_CITY_KM = 30
# A same-named .MOV recorded further than this from the photo is not its Live Photo clip
# (those are within seconds) but a separate video that shares the name after the iPhone
# counter wrapped, so it is filed on its own.
LIVE_PHOTO_MAX_GAP = datetime.timedelta(days=1)
# Month folder names; fixed English names, not the Mac's locale.
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

HERE = os.path.dirname(os.path.abspath(__file__))


def split(name):
    stem, dot, ext = name.rpartition(".")
    return (stem, ext.lower()) if dot else (name, "")


def read_tsv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [l.split("\t") for l in f.read().splitlines()[1:] if l]


def write_tsv(path, header, rows):
    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        f.writelines("\t".join(r) + "\n" for r in rows)


def append_tsv(path, header, rows):
    new = not os.path.exists(path)
    with open(path, "a", encoding="utf-8") as f:
        if new:
            f.write(header)
        f.writelines("\t".join(r) + "\n" for r in rows)


def read_metadata(paths):
    """Capture date + GPS via macOS ImageIO (handles HEIC) / AVFoundation (videos). Compiled once, then cached."""
    binary = os.path.join(HERE, ".bin", "meta")
    source = os.path.join(HERE, "meta.swift")
    if not os.path.exists(binary) or os.path.getmtime(binary) < os.path.getmtime(source):
        os.makedirs(os.path.dirname(binary), exist_ok=True)
        subprocess.run(["swiftc", "-O", source, "-o", binary], check=True)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("\n".join(paths))
        listfile = f.name
    try:
        out = subprocess.run([binary, listfile], check=True, capture_output=True, text=True).stdout
    finally:
        os.unlink(listfile)
    meta = {}
    for line in out.splitlines():
        path, date, src, lat, lon = line.split("\t")
        meta[path] = (date, src, float(lat) if lat else None, float(lon) if lon else None)
    return meta


class Cities:
    def __init__(self):
        self.grid = collections.defaultdict(list)
        with open(os.path.join(HERE, "..", "assets", "cities.tsv"), encoding="utf-8") as f:
            for line in f:
                name, lat, lon, _country = line.rstrip("\n").split("\t")
                lat, lon = float(lat), float(lon)
                self.grid[(math.floor(lat), math.floor(lon))].append((name, lat, lon))

    def nearest(self, lat, lon):
        best, best_km = None, MAX_CITY_KM
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for name, clat, clon in self.grid.get((math.floor(lat) + dy, math.floor(lon) + dx), ()):
                    km = haversine(lat, lon, clat, clon)
                    if km < best_km:
                        best, best_km = name, km
        return best


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(a))


def parse_exif_date(s):
    try:
        return datetime.datetime.strptime(s[:19], "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def safe_folder(name):
    return re.sub(r'[/\\:*?"<>|]', "-", name).strip(" .") or "Unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    draft = os.path.join(root, "draft")
    db_dir = os.path.join(root, ".photo-db")
    if not os.path.isdir(draft):
        sys.exit("No draft/ folder - run import_to_draft.py first.")
    hashes_path = os.path.join(db_dir, "draft-hashes.tsv")
    db_path = os.path.join(db_dir, "pictures.tsv")

    draft_hashes = {r[3]: r for r in read_tsv(hashes_path)}
    library = read_tsv(db_path)
    library_by_hash = {r[0]: r[2] for r in library}
    library_dates = {split(os.path.basename(r[2]))[0].lower(): r[3] for r in library if r[3]}

    files = sorted(e.name for e in os.scandir(draft) if e.is_file() and not e.name.startswith("."))
    file_set = set(files)
    groups = collections.defaultdict(list)
    for name in files:
        groups[split(name)[0].lower()].append(name)

    def media_of(members):
        """The files filed on their own: images, or for a group without one, its videos."""
        imgs = [m for m in members if split(m)[1] in IMAGE_EXTS]
        return imgs or [m for m in members if split(m)[1] in VIDEO_EXTS]

    media = {m for members in groups.values() for m in media_of(members)}

    # .MOVs sharing an image's name: Live Photo clips, unless their recording date says otherwise.
    live_candidates = {m for members in groups.values() if any(split(x)[1] in IMAGE_EXTS for x in members)
                       for m in members if split(m)[1] in VIDEO_EXTS}
    print(f"Reading dates/GPS of {len(media) + len(live_candidates)} images/videos...", flush=True)
    meta = read_metadata([os.path.join(draft, n) for n in sorted(media | live_candidates)])
    cities = Cities()

    def hashed(name):
        row = draft_hashes.get(name)
        st = os.stat(os.path.join(draft, name))
        return bool(row) and row[1] == str(st.st_size) and row[2] == str(st.st_mtime_ns)

    def mtime(name):
        return datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(draft, name)))

    def exif_date(name):
        p = os.path.join(draft, name)
        return parse_exif_date(meta[p][0]) if p in meta and meta[p][0] else None

    def closest(candidates, target):
        """(date, item) nearest in time to target. Same-named files from different years exist
        because the iPhone counter wraps at 9999, so the name alone can't pick the right one."""
        return min(candidates, key=lambda c: abs((c[0] - target).total_seconds()))

    def capture_date(name):
        d = exif_date(name)
        if d:
            return d, meta[os.path.join(draft, name)][1]
        # iPhone edited copy IMG_E1234 has no date: borrow the original IMG_1234's.
        m = re.match(r"(?i)^(IMG_)E(\d+)$", split(name)[0])
        if m:
            orig = (m.group(1) + m.group(2)).lower()
            candidates = [(exif_date(o), o) for o in groups.get(orig, [])
                          if split(o)[1] in IMAGE_EXTS and exif_date(o)]
            if orig in library_dates:
                try:
                    candidates.append((datetime.datetime.strptime(library_dates[orig][:19], "%Y-%m-%d %H:%M:%S"), None))
                except ValueError:
                    pass
            if candidates:
                return closest(candidates, mtime(name))[0], "original"
        return mtime(name), "file_modified"

    taken = set()  # destinations claimed in this run (matters for dry runs)

    def stem_used(dest_dir, stem):
        """Any file named <stem>.* in dest_dir, on disk or claimed in this run."""
        prefix = os.path.join(dest_dir, stem + ".").lower()
        on_disk = os.path.isdir(dest_dir) and any(
            split(f)[0].lower() == stem.lower() for f in os.listdir(dest_dir) if not f.startswith("."))
        return on_disk or any(t.startswith(prefix) for t in taken)

    def free_name(dest_dir, stem, exts, alone=False):
        """alone: the stem must be unused by any file type, so a separate video never sits
        next to a same-named photo and passes for its Live Photo clip."""
        candidate, n = stem, 1
        while (alone and stem_used(dest_dir, candidate)) or any(
                os.path.exists(os.path.join(dest_dir, f"{candidate}.{e}"))
                or os.path.join(dest_dir, f"{candidate}.{e}").lower() in taken for e in exts):
            n += 1
            candidate = f"{stem}-{n}"
        for e in exts:
            taken.add(os.path.join(dest_dir, f"{candidate}.{e}").lower())
        return candidate

    # Same-named .MOVs recorded far from every photo of that name are separate videos.
    separate = set()
    for members in groups.values():
        imgs = [m for m in members if split(m)[1] in IMAGE_EXTS]
        for v in members:
            if v in live_candidates and exif_date(v):
                if min(abs(exif_date(v) - capture_date(i)[0]) for i in imgs) > LIVE_PHOTO_MAX_GAP:
                    separate.add(v)
    media |= separate

    # Images/videos whose hash is missing or stale are left in draft for the hasher.
    unhashed = [name for name in files if name in media and not hashed(name)]
    unhashed_set = set(unhashed)

    # Build the plan: list of (image, companions, sha, dest_dir, kind, date, date_src, city)
    plan, seen = [], {}
    orphans = []
    batches = []  # (files filed on their own, companions to share out among them)
    for key in sorted(groups):
        members = groups[key]
        own = media_of(members)
        if not own:
            orphans += members
            continue
        batches.append((own, [m for m in members if m not in own and m not in separate
                              and split(m)[1] in COMPANION_EXTS]))
        batches += [([v], []) for v in sorted(members) if v in separate]
    for own, comps in batches:
        imgs = [m for m in own if m not in unhashed_set]
        if not imgs:
            continue
        imgs.sort(key=lambda m: PRIMARY_ORDER.index(split(m)[1]) if split(m)[1] in PRIMARY_ORDER else 99)
        dates = {img: capture_date(img) for img in imgs}
        attached = {img: [] for img in imgs}
        for c in comps:  # each .MOV/.AAE goes with the same-named photo closest to it in time
            attached[closest([(dates[i][0], i) for i in imgs], mtime(c))[1]].append(c)
        for img in imgs:
            sha = draft_hashes[img][0]
            date, date_src = dates[img]
            _, _, lat, lon = meta[os.path.join(draft, img)]
            city = cities.nearest(lat, lon) if lat is not None else None
            if sha in library_by_hash or sha in seen:
                original = library_by_hash.get(sha) or seen[sha]
                plan.append((img, attached[img], sha, "duplicates", "dup", date, date_src, city, original))
            else:
                parts = ["media", f"{date:%Y}", MONTHS[date.month - 1]] + ([safe_folder(city)] if city else [])
                dest = os.path.join(*parts)
                plan.append((img, attached[img], sha, dest, "new", date, date_src, city, None))
                seen[sha] = None  # filled with the final path below
        # leftover companions with no owner stay put (only when the group had no hashed image)

    # Resolve final names and execute.
    now = datetime.datetime.now()
    stamp = now.isoformat(timespec="seconds")
    new_rows, dup_rows, log_lines, moved_names = [], [], [], set()
    stats = collections.Counter()
    months, city_counts, date_sources = collections.Counter(), collections.Counter(), collections.Counter()
    examples = []
    for img, comps, sha, dest_rel, kind, date, date_src, city, original in plan:
        dest_dir = os.path.join(root, dest_rel)
        stem = split(img)[0]
        exts = [img.rpartition(".")[2]] + [c.rpartition(".")[2] for c in comps]
        final_stem = free_name(dest_dir, stem, exts, alone=split(img)[1] in VIDEO_EXTS)
        if not args.dry_run:
            os.makedirs(dest_dir, exist_ok=True)
        for name in [img] + comps:
            dest_name = f"{final_stem}.{name.rpartition('.')[2]}"
            rel = os.path.join(dest_rel, dest_name)
            if not args.dry_run:
                os.rename(os.path.join(draft, name), os.path.join(dest_dir, dest_name))
                side = os.path.join(draft, "._" + name)
                if os.path.exists(side) and not os.path.exists(os.path.join(dest_dir, "._" + dest_name)):
                    os.rename(side, os.path.join(dest_dir, "._" + dest_name))
            log_lines.append(f"{stamp}\tmover\tdraft/{name}\t{rel}\n")
            moved_names.add(name)
            if name == img:
                img_rel = rel
        stats[kind] += 1
        stats["companions"] += len(comps)
        if split(img)[1] in VIDEO_EXTS:
            stats[kind + "_video"] += 1
        if kind == "new":
            if sha in seen:
                seen[sha] = img_rel
            new_rows.append([sha, draft_hashes[img][1], img_rel, f"{date:%Y-%m-%d %H:%M:%S}",
                             date_src, city or "", stamp])
            months[f"{date:%Y/%m}"] += 1
            date_sources[date_src] += 1
            if city:
                city_counts[city] += 1
        else:
            dup_rows.append([sha, img_rel, original or seen.get(sha) or "", stamp])
        if len(examples) < 12:
            examples.append(f"  draft/{img} -> {img_rel}" + (f"  (+{len(comps)} companion)" if comps else ""))

    if not args.dry_run:
        append_tsv(db_path, DB_HEADER, new_rows)
        append_tsv(os.path.join(db_dir, "duplicates.tsv"), DUP_HEADER, dup_rows)
        with open(os.path.join(db_dir, "moves.log"), "a", encoding="utf-8") as f:
            f.writelines(log_lines)
        write_tsv(hashes_path, "sha256\tsize\tmtime_ns\tname\n",
                  [r for n, r in sorted(draft_hashes.items()) if n not in moved_names and n in file_set])

    print(("DRY RUN (nothing moved)" if args.dry_run else "Done") + ":")
    print(f"  {stats['new']} new images/videos -> media/ (of which {stats['new_video']} videos)")
    print(f"  {stats['dup']} duplicates -> duplicates/ (of which {stats['dup_video']} videos)")
    print(f"  {stats['companions']} companion files (.MOV/.AAE) moved with their photos")
    if separate:
        print(f"  {len(separate)} .MOVs share a photo's name but were recorded over a day apart - filed as separate videos")
    if new_rows:
        print("  Dates came from: " + ", ".join(f"{k} {v}" for k, v in date_sources.most_common()))
        print(f"  With a city folder: {sum(city_counts.values())}, month root (no GPS): {stats['new'] - sum(city_counts.values())}")
        print("  Busiest months: " + ", ".join(f"{k} ({v})" for k, v in months.most_common(6)))
        if city_counts:
            print("  Top cities: " + ", ".join(f"{k} ({v})" for k, v in city_counts.most_common(8)))
    if examples:
        print("Examples:")
        print("\n".join(examples))
    if unhashed:
        print(f"Left in draft/: {len(unhashed)} images/videos have no up-to-date hash - run hash_draft.py, then move_from_draft.py again.")
    if orphans:
        print(f"Left in draft/: {len(orphans)} files with no matching photo or video (e.g. lone .AAE), e.g. {orphans[0]}")


if __name__ == "__main__":
    main()
