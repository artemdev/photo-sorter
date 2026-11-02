# TODO

Planned work, roughly in order. Nothing here is built yet.

## 1. Local web dashboard

A small app that runs on your Mac and opens in the browser, so the whole workflow can be driven with buttons instead of terminal commands.

**Decisions made**
- It's a local web app: a **React + TypeScript (Vite)** frontend and a Python (FastAPI) backend bound to `127.0.0.1` only.
- In development, Vite serves the React app and proxies `/api` to the Python server. For everyday use, `npm run build` once and the Python server serves the built files, so `run.sh` starts one process and opens the browser (no Node needed to run it).
- Frontend libraries: TanStack Query for API calls and live job status, and a virtualized grid (e.g. `react-virtuoso`) so the library stays fast with thousands of thumbnails.
- It calls the same `photo_sorter` functions the CLI uses. The dashboard never moves files itself (the one exception is Trash, below), so `moves.log` and `.photo-db/` stay consistent. No Claude/AI is needed to use it.
- The server refuses any path that isn't on the selected drive.

**Planned layout**
```
dashboard/
  server/
    main.py      FastAPI routes; also serves web/dist in normal use
    jobs.py      runs one script at a time, streams its output to the page
    library.py   reads .photo-db/*.tsv for find / view / duplicates
    thumbs.py    thumbnails via macOS `sips` (handles HEIC), cached on the drive
  web/           React + TypeScript (Vite)
    src/pages/   DrivePicker, Sort, Library, Duplicates
    src/api/     typed API client + TanStack Query hooks
run.sh           builds web/ if needed, starts the server, opens the browser
```

**Screens**
- [ ] **Drive picker:** cards from `list_drives.py --json` showing name, size, loose photos and videos on the root, and whether a library exists. Read-only (NTFS) drives are greyed out.
- [ ] **Sort**
  - [ ] *Preview* runs the dry runs and shows what would happen.
  - [ ] *Sort now* runs import → hash → move with a live log and progress. It always shows the dry-run plan first and waits for confirmation, and warns when the plan looks wrong (e.g. most files dated in the future, or many without a hash).
  - [ ] Ends with a summary: imported, new, duplicates, busiest months, top cities, anything left on the root or in draft.
  - [ ] Smaller buttons: clear leftovers, rebuild database, upgrade old layout.
- [ ] **Library (view + find):** a thumbnail grid from `pictures.tsv`.
  - [ ] Filters: year / month, city, file name, photo vs video.
  - [ ] Click a thumbnail to open it full size with its date, city and path. Videos play inline.
- [ ] **Duplicates**
  - [ ] Each copy shown beside its original (from `duplicates.tsv`).
  - [ ] Tick copies, then *Move to Trash* (macOS Trash, recoverable; never permanent delete). Log each to `moves.log` and drop it from `duplicates.tsv`.

**Safety and errors**
- [ ] Only one job runs at a time, and buttons are disabled while it runs.
- [ ] A failing script stops the run, shows the error line, and suggests a fix (e.g. Files and Folders permission for removable volumes).
- [ ] The drive being unplugged mid-run shows a clear message instead of crashing.

## 2. Tests

- [ ] pytest suite that builds a fake drive in a temp folder from generated sample images (never real photos).
- [ ] Cover import (incl. Live Photo `.MOV` / `.AAE` grouping and name clashes), hashing (resume, skip unchanged), filing by date and city, duplicate detection, leftovers, layout upgrade, and dry runs moving nothing.
- [ ] Dashboard: API tests for find / duplicates / trash, and the path guard.
- [ ] Dashboard UI: component tests (Vitest + React Testing Library) for the sort flow, filters and the duplicate review.

## 3. CLI with simple install

Turn the separate scripts into one `photo-sorter` command that anyone can install and use without cloning the repo or knowing Python.

**Install**
- [x] Python package (`pyproject.toml`) with a `photo-sorter` command; installs with `pipx install git+https://github.com/artemdev/photo-sorter`.
- [x] Ship `cities.tsv` and `meta.swift` inside the package. The Swift helper is compiled once into `~/Library/Caches/photo-sorter/`.
- [ ] Publish to PyPI so it's just `pipx install photo-sorter` (or `uv tool install photo-sorter`).
- [ ] Swift helper: ship a prebuilt universal (Intel + Apple Silicon) binary in the package, so users don't need Xcode tools. Fall back to compiling `meta.swift` only if the binary can't run.
- [ ] Later: a Homebrew tap (`brew install artemdev/tap/photo-sorter`).

**Usage** (done unless marked)
```sh
photo-sorter                          # pick a drive from a list, preview, confirm, sort
photo-sorter sort "/Volumes/MY DRIVE" # same, for a given drive
photo-sorter preview <drive>          # show what would happen, move nothing
photo-sorter drives                   # list connected drives
photo-sorter import|hash|move <drive> # single steps
photo-sorter leftovers <drive>        # move lone .AAE files to leftovers/
photo-sorter rebuild-db | upgrade <drive>
photo-sorter undo <drive>             # TODO: undo the last run from moves.log
photo-sorter dashboard                # TODO: open the web dashboard
```
- [x] `sort` runs import → hash → move, shows each dry-run plan first and asks before moving (`--yes` to skip). Stops and points to `upgrade` on an older library layout.
- [x] Friendly errors instead of tracebacks: drive not found or unplugged, read-only drive (NTFS), missing macOS permission (with the System Settings path), missing Xcode tools, Ctrl-C.
- [x] `--help` for every command with examples; `photo-sorter --version`.
- [ ] Progress bars for import and hashing (hashing prints a count every 500 files today).
- [ ] A short plain-language summary at the end of `sort` (the same report the agent writes), instead of each step's own output.
- [ ] An `undo` command that replays `moves.log` backwards.

**Code**
- [x] Move the scripts into a package (`photo_sorter/`) as importable modules.
- [x] Keep `scripts/*.py` working as thin wrappers, so the agent in `agent/` keeps working.
- [x] README: one-line install and `photo-sorter`.
- [ ] Let the modules return results instead of printing, so the CLI and the dashboard share one summary format.
- [ ] Share one copy of `IMAGE_EXTS` / `VIDEO_EXTS` (currently repeated in `importer.py`, `hasher.py`, `mover.py` and `drives.py`).
- [ ] Switch the agent from `scripts/*.py` to the `photo-sorter` command, then remove the wrappers.

## 4. Later

- [ ] Linux / Windows support (`meta.swift` and `list_drives.py` are macOS-only today; e.g. use exiftool there).
- [ ] Near-duplicate detection (resized or re-encoded copies), not just byte-for-byte.
- [ ] A Claude Code agent button in the dashboard for a written report / questions about the library.
