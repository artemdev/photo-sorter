"""The `photo-sorter` command.

Run it with no arguments to pick a drive, see a preview and sort it. Every other
command runs one step on its own. Nothing is ever deleted; every move is logged
to <drive>/.photo-db/moves.log.
"""
import argparse
import errno
import os
import re
import subprocess
import sys

from . import __version__, drives, hasher, importer, leftovers, mover, upgrade

EXAMPLES = """\
examples:
  photo-sorter                           pick a drive, preview, confirm, sort
  photo-sorter sort "/Volumes/MY DRIVE"  the same for a given drive
  photo-sorter preview "/Volumes/MY DRIVE"
  photo-sorter drives                    list connected drives
"""


def pick_drive():
    found = drives.find_drives()
    if not found:
        sys.exit("No external drives found. Plug one in, or pass a folder: photo-sorter sort /path/to/folder")
    print("Connected drives:\n")
    for i, d in enumerate(found, 1):
        drives.print_drive(i, d)
    print()
    while True:
        try:
            answer = input(f"Which drive? [1-{len(found)}, Enter to cancel]: ").strip()
        except EOFError:
            answer = ""
        if not answer:
            print("Cancelled.")
            raise SystemExit(0)
        if answer.isdigit() and 1 <= int(answer) <= len(found):
            break
        print("Type one of the numbers above.")
    d = found[int(answer) - 1]
    if not d["writable"]:
        sys.exit(f"{d['name']} is read-only (often NTFS), so files can't be moved on it.")
    return d["path"]


def resolve(drive):
    if drive is None:
        return pick_drive()
    path = os.path.abspath(os.path.expanduser(drive))
    if not os.path.isdir(path):
        sys.exit(f"Not found: {path}\nRun `photo-sorter drives` to see connected drives.")
    return path


def confirm(question, yes):
    if yes:
        return True
    try:
        return input(f"\n{question} [y/N]: ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def heading(text):
    print(f"\n== {text}", flush=True)


def loose_media(root):
    """Images and videos lying loose on the drive root."""
    exts = importer.IMAGE_EXTS | importer.VIDEO_EXTS
    return sum(1 for e in os.scandir(root) if e.is_file(follow_symlinks=False)
               and not e.name.startswith(".") and importer.split(e.name)[1] in exts)


def in_draft(root):
    draft = os.path.join(root, "draft")
    return os.path.isdir(draft) and any(not n.startswith(".") for n in os.listdir(draft))


def needs_upgrade(root):
    """True for a library made by an older version (pictures/ or numbered month folders)."""
    if os.path.isdir(os.path.join(root, "pictures")):
        return True
    media = os.path.join(root, "media")
    if not os.path.isdir(media):
        return False
    return any(re.fullmatch(r"0[1-9]|1[0-2]", m)
               for y in os.listdir(media) if re.fullmatch(r"\d{4}", y) and os.path.isdir(os.path.join(media, y))
               for m in os.listdir(os.path.join(media, y)))


def check_layout(root):
    if needs_upgrade(root):
        sys.exit("This drive uses an older folder layout (pictures/ or month folders like 07).\n"
                 f"Upgrade it first: photo-sorter upgrade \"{root}\"")


def cmd_sort(args):
    root = resolve(args.drive)
    check_layout(root)
    if not loose_media(root) and not in_draft(root):
        print(f"Nothing to sort: no loose photos or videos on {root}.")
        return
    if loose_media(root):
        heading("Step 1 of 3: collect loose photos and videos into draft/ (preview)")
        importer.main([root, "--dry-run"])
        if not confirm("Move these into draft/?", args.yes):
            print("Stopped. Nothing was moved.")
            return
        importer.main([root])
    heading("Step 2 of 3: fingerprint files to find duplicates")
    hasher.main([root])
    heading("Step 3 of 3: sort into media/ and duplicates/ (preview)")
    mover.main([root, "--dry-run"])
    if not confirm("Sort these files now?", args.yes):
        print("Stopped. Your files are waiting in draft/; run `photo-sorter sort` again to finish.")
        return
    mover.main([root])
    print("\nAll done. Duplicates are in duplicates/ for you to review. "
          "Every move is logged in .photo-db/moves.log.")


def cmd_preview(args):
    root = resolve(args.drive)
    check_layout(root)
    heading("Loose files on the root that would go to draft/")
    importer.main([root, "--dry-run"])
    if in_draft(root):
        heading("Files already in draft/ and where they would go")
        hasher.main([root])
        mover.main([root, "--dry-run"])
    elif loose_media(root):
        print("\nWhere each file lands (media/ or duplicates/) is decided after they're collected "
              "and fingerprinted, so run `photo-sorter sort` to see that plan before anything is filed.")
    print("\nPreview only: nothing was moved.")


def step(module, dry_run_flag=True):
    def run(args):
        root = resolve(args.drive)
        module.main([root] + (["--dry-run"] if dry_run_flag and args.dry_run else []))
    return run


def cmd_move(args):
    root = resolve(args.drive)
    check_layout(root)
    mover.main([root] + (["--dry-run"] if args.dry_run else []))


def cmd_rebuild_db(args):
    hasher.main([resolve(args.drive), "--rebuild-db"])


def cmd_drives(args):
    drives.main(["--json"] if args.json else [])


def build_parser():
    ap = argparse.ArgumentParser(
        prog="photo-sorter",
        description="Sort the photos and videos on an external drive into media/YYYY/<Month>/<City>/, "
                    "with exact copies moved to duplicates/. Nothing is ever deleted.",
        epilog=EXAMPLES, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"photo-sorter {__version__}")
    sub = ap.add_subparsers(dest="command", metavar="<command>")

    def add(name, func, help, drive=True, dry_run=False, yes=False):
        p = sub.add_parser(name, help=help, description=help)
        if drive:
            p.add_argument("drive", nargs="?", help="drive or folder (asks if left out)")
        if dry_run:
            p.add_argument("--dry-run", action="store_true", help="show what would happen, move nothing")
        if yes:
            p.add_argument("-y", "--yes", action="store_true", help="don't ask before moving files")
        p.set_defaults(func=func)
        return p

    add("sort", cmd_sort, "collect, fingerprint and sort a drive (previews and asks first)", yes=True)
    add("preview", cmd_preview, "show what sorting would do, move nothing")
    p = add("drives", cmd_drives, "list connected external drives", drive=False)
    p.add_argument("--json", action="store_true", help="output as JSON")
    add("import", step(importer), "only collect loose photos and videos from the root into draft/", dry_run=True)
    add("hash", step(hasher, dry_run_flag=False), "only fingerprint the files in draft/ (read-only)")
    add("move", cmd_move, "only sort fingerprinted files from draft/ into media/ and duplicates/", dry_run=True)
    add("leftovers", step(leftovers), "move lone .AAE edit files from the root into leftovers/", dry_run=True)
    add("rebuild-db", cmd_rebuild_db, "re-index media/ after you changed it by hand (slow)")
    add("upgrade", step(upgrade), "upgrade an older library: pictures/ -> media/, 07 -> July", dry_run=True)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command is None:  # plain `photo-sorter`: the guided sort
        args = build_parser().parse_args(["sort"] + ([] if argv is None else list(argv)))
    if sys.platform != "darwin":
        sys.exit("photo-sorter works on macOS only for now.")
    try:
        args.func(args)
    except KeyboardInterrupt:
        sys.exit("\nStopped. Every move so far is logged in .photo-db/moves.log; "
                 "run the same command again to continue.")
    except PermissionError as e:
        sys.exit(f"No permission to access {e.filename or 'the drive'}.\n"
                 "Allow your terminal in System Settings > Privacy & Security > Files and Folders "
                 "(Removable Volumes), then try again.")
    except OSError as e:
        if e.errno == errno.EROFS:
            sys.exit("This drive is read-only (often NTFS), so files can't be moved on it.")
        if e.errno in (errno.ENOENT, errno.ENXIO, errno.EIO) and e.filename:
            sys.exit(f"Lost access to {e.filename}. Was the drive unplugged? "
                     "Plug it back in and run the same command again.")
        raise
    except subprocess.CalledProcessError:
        sys.exit("Reading photo dates failed. Try `xcode-select --install`, then run the same command again.")


if __name__ == "__main__":
    main()
