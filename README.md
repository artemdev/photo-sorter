# photo-sorter

If you copy photos from your phone to an external drive, they pile up in one messy folder, often with the same photo saved several times. photo-sorter tidies that up: it puts every photo and video into a folder named after the year, month and city where it was taken, for example `media/2024/July/Oslo/`, and moves exact copies into a separate `duplicates/` folder.

It never deletes anything. It shows you a preview and asks before moving files, and every move is written to a log so it can be undone. Your existing folders on the drive are left alone; only loose files are sorted. City names are looked up offline, so nothing leaves your computer.

## Install

You need a Mac with Python 3.9+, the Xcode Command Line Tools and [pipx](https://pipx.pypa.io/). If you don't have them yet:

```sh
xcode-select --install
brew install pipx && pipx ensurepath   # then open a new terminal window
```

Then install photo-sorter and check it works:

```sh
pipx install git+https://github.com/artemdev/photo-sorter
photo-sorter --version
```

To update later, run `pipx upgrade photo-sorter`. If pipx warns about a space in its home path, that's harmless on macOS; to silence it, add `export PIPX_HOME="$HOME/.local/pipx"` to `~/.zshrc` before installing.

## Use

Plug in your drive and run:

```sh
photo-sorter
```

It lists your drives, lets you pick one, shows what it will do, and asks before moving anything. Other commands:

```sh
photo-sorter preview "/Volumes/MY DRIVE"   # see what would happen, move nothing
photo-sorter drives                        # list connected drives
photo-sorter --help                        # all commands
```

You can also let a Claude Code agent do this for you (see `agent/`). Next on the list is a simple dashboard with buttons for sorting, searching, viewing photos and cleaning up duplicates; see [TODO.md](TODO.md).

MIT licensed. City data comes from [GeoNames](https://www.geonames.org/) (CC BY 4.0).
