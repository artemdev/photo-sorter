#!/usr/bin/env python3
"""List external / removable drives that photo-import can work on.

For each mounted volume that isn't the internal system disk, prints name, path,
format, size, free space, writable or not, images and videos loose on its root, and whether
it already has a photo database (.photo-db/pictures.tsv). Read-only.

Usage: list_drives.py [--json]
"""
import json
import os
import plistlib
import subprocess
import sys

IMAGE_EXTS = {
    "jpg", "jpeg", "heic", "heif", "png", "gif", "tif", "tiff", "webp", "bmp",
    "dng", "cr2", "cr3", "nef", "arw", "raf", "orf", "rw2", "srw", "pef",
}
VIDEO_EXTS = {"mov", "mp4", "m4v", "3gp", "avi", "mkv", "mts", "m2ts", "wmv", "webm"}


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1000


def info(path):
    out = subprocess.run(["diskutil", "info", "-plist", path], capture_output=True).stdout
    return plistlib.loads(out) if out else {}


def main():
    drives = []
    for name in sorted(os.listdir("/Volumes")):
        path = os.path.join("/Volumes", name)
        if not os.path.ismount(path) or os.path.realpath(path) == "/":
            continue
        d = info(path)
        if not d or (d.get("Internal") and not d.get("RemovableMedia")):
            continue  # internal disks (system, data) are not photo drives
        fs = d.get("FilesystemName") or d.get("FilesystemType") or "?"
        try:
            names = [e.name for e in os.scandir(path) if e.is_file() and not e.name.startswith(".")]
            image_stems = {n.rpartition(".")[0].lower() for n in names
                           if n.rpartition(".")[2].lower() in IMAGE_EXTS}
            root_images = len([n for n in names if n.rpartition(".")[2].lower() in IMAGE_EXTS])
            # Videos sharing an image's name are Live Photo companions, not separate videos.
            root_videos = len([n for n in names if n.rpartition(".")[2].lower() in VIDEO_EXTS
                               and n.rpartition(".")[0].lower() not in image_stems])
        except PermissionError:
            root_images = root_videos = None
        db = os.path.join(path, ".photo-db", "pictures.tsv")
        library = None
        if os.path.exists(db):
            with open(db, encoding="utf-8") as f:
                library = max(sum(1 for _ in f) - 1, 0)
        drives.append({
            "name": name,
            "path": path,
            "format": fs,
            "size": human(d.get("TotalSize", 0)),
            "free": human(d.get("APFSContainerFree") or d.get("FreeSpace", 0)),
            "writable": bool(d.get("WritableVolume", d.get("Writable", True))),
            "connection": d.get("BusProtocol", "?"),
            "root_images": root_images,
            "root_videos": root_videos,
            "library_photos": library,
        })

    if "--json" in sys.argv:
        print(json.dumps(drives, indent=2, ensure_ascii=False))
        return
    if not drives:
        print("No external or removable drives are mounted. Plug one in and try again.")
        return
    for i, d in enumerate(drives, 1):
        notes = []
        if not d["writable"]:
            notes.append("READ-ONLY - can't move files" + (" (NTFS)" if "NTFS" in d["format"].upper() else ""))
        if d["root_images"] is None:
            notes.append("no permission to read - grant access in System Settings")
        print(f"{i}. {d['name']}  ({d['path']})")
        print(f"   {d['format']}, {d['connection']}, {d['size']} total, {d['free']} free")
        print(f"   Images on root: {d['root_images'] if d['root_images'] is not None else '?'}"
              f" | Videos on root: {d['root_videos'] if d['root_videos'] is not None else '?'}"
              f" | Photo database: {str(d['library_photos']) + ' photos/videos' if d['library_photos'] is not None else 'none yet'}")
        for n in notes:
            print(f"   ! {n}")


if __name__ == "__main__":
    main()
