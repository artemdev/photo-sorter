# photo-sorter

Sorts the photos and videos on an external drive into a tidy, de-duplicated library on macOS.

Loose files on the drive root are moved into `draft/`, fingerprinted with SHA-256, and then filed by capture date and place:

```
media/2024/July/Oslo/IMG_1234.HEIC
media/2024/July/IMG_1240.MOV        (no GPS → no city folder)
duplicates/IMG_1234-2.HEIC          (byte-for-byte copy of something already in media/)
```

It's built for people who copy photos off phones onto an external drive and end up with thousands of loose, duplicated files. Nothing is ever deleted. Every move is logged so it can be undone.

## Features

- **Import:** moves loose images and videos from the drive root into `draft/`. Live Photo `.MOV` clips and iPhone `.AAE` edits travel with their photo. Existing folders on the drive are never touched.
- **Hash:** SHA-256 per file. The work is resumable, and unchanged files are skipped.
- **File:** sorts by EXIF capture date (photos) or recording date (videos) into `media/YYYY/<Month>/<City>/`. The city is the nearest town over 5,000 people within 30 km, looked up **offline**.
- **Duplicates:** exact copies go to `duplicates/`, logged against the original they match.
- **Dry run:** `--dry-run` on every step that moves files.
- **Plain-text database:** `.photo-db/` on the drive holds `pictures.tsv`, `duplicates.tsv` and `moves.log`, which you can open in Numbers or Excel.

## Requirements

- macOS (uses ImageIO/AVFoundation for HEIC and video metadata)
- Python 3.9+ (standard library only)
- Xcode Command Line Tools (`xcode-select --install`) for `swiftc`. A small Swift helper is compiled automatically on first run into `scripts/.bin/`.

## Usage

```sh
# 1. Find the drive
python3 scripts/list_drives.py

# 2. Import loose files from the root into draft/ (preview first)
python3 scripts/import_to_draft.py "/Volumes/MY DRIVE" --dry-run
python3 scripts/import_to_draft.py "/Volumes/MY DRIVE"

# 3. Hash everything in draft/ (read-only; re-run if interrupted)
python3 scripts/hash_draft.py "/Volumes/MY DRIVE"

# 4. File into media/ or duplicates/ (preview first)
python3 scripts/move_from_draft.py "/Volumes/MY DRIVE" --dry-run
python3 scripts/move_from_draft.py "/Volumes/MY DRIVE"
```

Other tools:

| Script | What it does |
|---|---|
| `clear_leftovers.py <drive> [--dry-run]` | Moves lone `.AAE` edit files (no matching photo) from the root into `leftovers/` |
| `hash_draft.py <drive> --rebuild-db` | Re-indexes `media/` after you changed it by hand |
| `upgrade_layout.py <drive> [--dry-run]` | Upgrades older libraries: `pictures/` → `media/`, `07` → `July` |

macOS may ask the terminal for access to removable volumes. Grant it in **System Settings → Privacy & Security → Files and Folders**.

### With Claude Code

`agent/media-import.md` is a Claude Code subagent that runs the whole import → hash → move → verify workflow and writes a plain-language report. Copy it to `~/.claude/agents/` and edit the script paths to match where you cloned this repo.

## Project layout

```
scripts/   the import / hash / move tools (Python + one Swift helper)
assets/    cities.tsv, offline place names for the city lookup
agent/     Claude Code subagent definition
```

## Plans

See [TODO.md](TODO.md). Next up is a local web dashboard for sorting, searching, viewing and cleaning up duplicates.

## License

MIT, see [LICENSE](LICENSE).

`assets/cities.tsv` is derived from [GeoNames](https://www.geonames.org/) data, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
