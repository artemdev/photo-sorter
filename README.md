# photo-sorter

If you copy photos from your phone to an external drive, they pile up in one messy folder, often with the same photo saved several times. photo-sorter tidies that up: it puts every photo and video into a folder named after the year, month and city where it was taken, for example `media/2024/July/Oslo/`, and moves exact copies into a separate `duplicates/` folder.

It never deletes anything. Every move is written to a log, so it can be undone, and you can preview what will happen before anything moves. Your existing folders on the drive are left alone; only loose files are sorted. City names are looked up offline, so nothing leaves your computer.

It runs on macOS and is written in Python, with a small Swift helper that reads photo dates and GPS. You need Python 3 and the Xcode Command Line Tools (`xcode-select --install`). To sort a drive, preview first and then run each step:

```sh
python3 scripts/import_to_draft.py "/Volumes/MY DRIVE" --dry-run   # preview
python3 scripts/import_to_draft.py "/Volumes/MY DRIVE"             # collect loose files
python3 scripts/hash_draft.py "/Volumes/MY DRIVE"                  # find duplicates
python3 scripts/move_from_draft.py "/Volumes/MY DRIVE"             # sort into folders
```

You can also let a Claude Code agent do all of this for you (see `agent/`). Next on the list is a simple dashboard with buttons for sorting, searching, viewing photos and cleaning up duplicates; see [TODO.md](TODO.md).

MIT licensed. City data comes from [GeoNames](https://www.geonames.org/) (CC BY 4.0).
