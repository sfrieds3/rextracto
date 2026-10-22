# rextracto

[![CI](https://github.com/sfrieds3/rextracto/actions/workflows/ci.yml/badge.svg)](https://github.com/sfrieds3/rextracto/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/sfrieds3/rextracto?sort=semver)](https://github.com/sfrieds3/rextracto/releases)

Fuzzy-pick text from your terminal in [Rex](https://www.superlogical.com/rex). rextracto is a port of [extrakto](https://github.com/laktak/extrakto). It pulls words, paths, URLs, quoted strings and whole lines out of a pane's screen and scrollback, and lists them in [fzf](https://github.com/junegunn/fzf). Type a few letters to find the one you want, then insert it at the prompt, copy it, open it or edit it.

```text
┌──────────────────────────────────────────────────────────────────────┐
│   ~/src/app/config.toml                                              │
│   https://example.com/docs/setup                                     │
│ ▌ ./build/output/report.html                                         │
│   tab=insert, enter=copy, ^o=open, ^e=edit, ^f=filter [path], ^g=…   │
│ > rep                                                                │
└──────────────────────────────────────────────────────────────────────┘
```

## Features

- Filters: `word`, `all` (URLs, paths, quotes and so on, each labelled), `line`, and any you define. Ctrl-F switches between them.
- Grab areas: the screen plus recent history, all scrollback, or every pane in the tab. Ctrl-G switches between them.
- Newest matches come first, with duplicates removed. Shift-Tab picks several.
- Insert uses a Rex paste event, so bracketed paste works. Copying uses `pbcopy`, `wl-copy` or `xclip`, falling back to OSC 52.
- Filters use extrakto's `extrakto.conf` format, so an existing `~/.config/extrakto/extrakto.conf` keeps working.

## Requirements

- Rex with Lua configuration (`~/.config/rex/init.lua`)
- Python 3.10 or newer (standard library only)
- [fzf](https://github.com/junegunn/fzf) and `rex` on the pane's `PATH` (Rex adds `rex` to the panes it starts)

## Install

Clone the repository, or download a [release](https://github.com/sfrieds3/rextracto/releases):

```sh
git clone https://github.com/sfrieds3/rextracto ~/code/rextracto
```

Load it from `~/.config/rex/init.lua` and bind the `rextracto` action:

```lua
local root = os.getenv("HOME") .. "/code/rextracto"
package.path = root .. "/lua/?.lua;" .. package.path
require("rextracto").setup({ root = root })

rex.bind("cmd+shift+e", "rextracto")
```

Then run `rex config reload`. `setup` defines the action, and you bind it like any other Rex action: directly, or inside a mode such as a tmux-style prefix:

```lua
rex.mode("prefix", { exclusive = true })
rex.bind("ctrl+space", "client.mode.enter", { name = "prefix", once = true })
rex.bind("prefix/tab", "rextracto")
```

The action also shows up in the command palette as "Extract Text From This Pane". It opens fzf in a floating layer over the current tab. When you finish, the layer closes and focus returns to the pane.

## Usage

| Key | Action |
| --- | --- |
| Tab | insert the selection into the pane |
| Enter | copy the selection |
| Ctrl-O | open the selection with `open` or `xdg-open`, from the pane's working directory |
| Ctrl-E | type `$EDITOR -- <selection>` into the pane and press Enter |
| Ctrl-F | next filter |
| Ctrl-G | next grab area |
| Ctrl-H | help |
| Shift-Tab | select several entries; they're joined with spaces (newlines in `line` mode) |
| Esc, Ctrl-C | cancel |

### Filters

| Filter | Lists |
| --- | --- |
| `word` | runs of text without whitespace, brackets, `=`, `$` or box-drawing characters |
| `all` | every filter that has `in_all` set, each entry labelled (`url: …`, `path: …`). URLs also list their host as `url2: …`. |
| `line` | whole lines, trimmed |
| `path` | `~/x`, `/x/y`, `./x`, `a/b` and so on, excluding transfer rates like `5k/s` and fractions like `1/2` |
| `url` | `http(s)://`, `git@`, `git://`, `ssh://`, `(s)ftp://` and `file:///` |
| `quote`, `s-quote` | double- and single-quoted strings, with and without the quotes |

Only entries at least `min_length` characters long (5 by default) are listed.

### Grab areas

| Area | Text |
| --- | --- |
| `recent` | the screen and 10 lines of history |
| `full` | all of the pane's scrollback |
| `window recent`, `window full` | the same, plus the tab's other terminal panes |

Ctrl-G cycles recent → window recent → full → window full, the same order as extrakto. With one pane in the tab it skips the `window` areas.

## Configuration

Pass options to `setup`. Names follow extrakto's `@extrakto_*` options:

```lua
require("rextracto").setup({
  root = root,
  grab_area = "recent",
  filter_order = "path url word line",
  bounds = { 0.1, 0.5, 0.8, 0.45 },   -- bottom half of the window
  fzf_layout = "reverse",
  clip_tool = "~/bin/clipboard-copy",
})
```

| Option | Default | Notes |
| --- | --- | --- |
| `root` | | Checkout directory. Required: Rex doesn't give modules their file name. |
| `action` | `rextracto` | Name of the action to define. Call `setup` twice for two variants. |
| `bounds` | `{ 0.05, 0.05, 0.9, 0.9 }` | The popup as `{ x, y, width, height }` fractions of the window. |
| `grab_area` | `window full` | Area to start in. |
| `filter_order` | `word all line` | Filters Ctrl-F cycles through; the first is where it starts. |
| `min_length` | `5` | Shortest entry to list. |
| `clip_tool` | `pbcopy`, `wl-copy` or `xclip`, then OSC 52 | Shell command that copies its stdin. |
| `open_tool` | `open` or `xdg-open` | Opener command. |
| `editor` | `$EDITOR`, then `vi` | Editor typed by Ctrl-E. |
| `fzf_tool` | `fzf` | fzf command, with any extra flags. |
| `fzf_layout` | `default` | `default`, `reverse` or `reverse-list`. |
| `fzf_unset_default_opts` | `true` | Ignore `$FZF_DEFAULT_OPTS`. |
| `insert_key`, `copy_key`, `open_key`, `edit_key`, `filter_key`, `grab_key`, `help_key` | `tab`, `enter`, `ctrl-o`, `ctrl-e`, `ctrl-f`, `ctrl-g`, `ctrl-h` | fzf key names. |
| `python` | `python3` | Interpreter for the script. |

### Custom filters

Filters live in INI sections. rextracto reads its own `rextracto.conf`, then `~/.config/extrakto/extrakto.conf`, then `~/.config/rextracto/rextracto.conf`; later files override earlier ones key by key.

```ini
# ~/.config/rextracto/rextracto.conf
[ticket]
regex: \b([A-Z]{2,}-[0-9]+)\b

[word]
# also split words on commas
regex: ([^][(){}=$─-➿-⋅↴│, \t\n\r]+)
```

| Key | Meaning |
| --- | --- |
| `regex` | Python regex; the capture groups are joined to make the entry. Matching ignores case. |
| `enabled` | `false` turns the filter off. |
| `in_all` | `false` leaves it out of `all`. |
| `lstrip`, `rstrip` | characters to trim from either end |
| `exclude` | drop entries that match this regex |
| `alt2` … `alt9` | also list the first group of this regex, labelled `name2` … |

Add a custom filter to `filter_order` to cycle to it, or rely on `all`.

### Command line

`rextracto.py extract` reads text on stdin and takes `extrakto.py`'s flags, which helps when testing filters:

```sh
printf 'see ~/notes/todo.txt and https://example.com\n' | ./rextracto.py extract -pu
printf 'fix ABC-123 today\n' | ./rextracto.py extract -a ticket
```

## Troubleshooting

- **The popup shows an error instead of fzf.** Rex keeps a pane that fails quickly, so its error stays on screen. The usual cause is `fzf`, `python3` or `rex` missing from the pane's `PATH`; set `fzf_tool` or `python` to an absolute path.
- **"NO MATCH - use a different filter".** Nothing matched the current filter. Press Ctrl-F or Ctrl-G.
- **Copy does nothing over SSH.** Set `clip_tool`, or let it fall back to OSC 52.

## Development

```sh
python3 -m unittest discover -s tests -v   # filters (extrakto's fixtures), capture, picker keys
lua tests/test_lua.lua                     # the Rex action (lua5.1, luajit or nvim -l)
ruff check . && ruff format --check .
```

CI runs these on Linux and macOS for every push and pull request. Each push to `main` that has a `feat`, `fix` or breaking commit is tagged and released. The version bump follows [Conventional Commits](https://www.conventionalcommits.org): `fix` is a patch, `feat` a minor and `!`/`BREAKING CHANGE` a major.

## Credits

The filter engine, the default filters and the test fixtures come from [extrakto](https://github.com/laktak/extrakto) by Christian Zangl. See also [rex-thumbs](https://github.com/sfrieds3/rex-thumbs), for copying what's on screen with hints.

## License

[MIT](LICENSE)
