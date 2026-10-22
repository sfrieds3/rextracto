#!/usr/bin/env python3
"""Extract words, paths, URLs and lines from Rex panes and pick them with fzf, like extrakto.

usage: rextracto.py [options] SESSION BLOCK     pick from BLOCK (run from lua/rextracto.lua)
       rextracto.py extract [options] < TEXT     print tokens, like extrakto.py

The filter engine and rextracto.conf come from extrakto (MIT, Christian Zangl).
"""

import argparse
import base64
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from collections import OrderedDict
from configparser import ConfigParser

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REX = os.environ.get("REX_BIN") or "rex"
TIMEOUT = os.environ.get("REXTRACTO_TIMEOUT", "2s")
USER_CONFIGS = ("~/.config/extrakto/extrakto.conf", "~/.config/rextracto/rextracto.conf")
# In the order the grab key cycles through them, as in extrakto.
GRAB_AREAS = ("recent", "window recent", "full", "window full")
GRAB_AREA = re.compile(r"(window )?(recent|full|[0-9]+)")
RECENT_LINES = 10
HELP = """\
rextracto: pick text from the pane with fzf. Type a few keys to fuzzy match.

  {filter_key:<8} next filter: word (min length 5), all (quotes, urls, paths, ...), line, ...
  {grab_key:<8} next grab area: recent (screen and {recent} lines of history), window recent
           (also the other panes in this tab), full (all history), window full
  shift-tab select several entries
  esc      cancel

  {insert_key:<8} insert the selection into the pane
  {copy_key:<8} copy the selection to the clipboard
  {open_key:<8} open the selection with the system opener
  {edit_key:<8} type `$EDITOR -- selection` into the pane

Filters come from rextracto.conf; add your own in ~/.config/rextracto/rextracto.conf.
Ctrl-F order (filter_order): {filters}
"""


class ExtraktoException(Exception):
    pass


class Extrakto:
    def __init__(self, *, min_length=5, alt=False, prefix_name=False, configs=None):
        conf = ConfigParser(interpolation=None)
        if configs is None:
            configs = [os.path.join(SCRIPT_DIR, "rextracto.conf")] + [os.path.expanduser(path) for path in USER_CONFIGS]
        conf.read(configs)
        sections = conf.sections()
        if "path" not in sections or "url" not in sections:
            raise ExtraktoException("rextracto.conf incomplete, path and url must exist")

        self.min_length = min_length
        self.alt = alt
        self.prefix_name = prefix_name
        self.in_all = []
        self.fdict = {}
        for name in sections:
            section = conf[name]
            alts = [section[f"alt{index}"] for index in range(2, 10) if f"alt{index}" in section]
            if section.getboolean("in_all", fallback=True):
                self.in_all.append(name)
            if section.getboolean("enabled", fallback=True):
                self.fdict[name] = FilterDef(
                    self,
                    name,
                    regex=section.get("regex"),
                    exclude=section.get("exclude", ""),
                    lstrip=section.get("lstrip", ""),
                    rstrip=section.get("rstrip", ""),
                    alt=alts,
                )

    def __getitem__(self, key):
        if key not in self.fdict:
            raise ExtraktoException(f"Unknown filter {key}")
        return self.fdict[key]

    def all(self):
        return self.in_all

    def keys(self):
        return list(self.fdict)


class FilterDef:
    def __init__(self, extrakto, name, *, regex, exclude, lstrip, rstrip, alt):
        self.extrakto = extrakto
        self.name = name
        self.regex = regex
        self.exclude = exclude
        self.lstrip = lstrip
        self.rstrip = rstrip
        self.alt = alt

    def filter(self, text):
        res = []

        def add(name, value):
            res.append(f"{name}: {value}" if self.extrakto.prefix_name else value)

        for match in re.finditer(self.regex, "\n" + text, flags=re.I):
            item = "".join(filter(None, match.groups()))
            # strip invalid characters (like punctuation or markdown syntax)
            if self.lstrip:
                item = item.lstrip(self.lstrip)
            if self.rstrip:
                item = item.rstrip(self.rstrip)
            if len(item) < self.extrakto.min_length or (self.exclude and re.search(self.exclude, item, re.I)):
                continue
            if self.extrakto.alt:
                for index, altre in enumerate(self.alt):
                    found = re.search(altre, item)
                    if found:
                        add(f"{self.name}{index + 2}", found[1])
            add(self.name, item)
        return res


def get_lines(text, *, min_length=5, prefix_name=False):
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if len(line) >= min_length:
            lines.append("line: " + line if prefix_name else line)
    return lines


def extract(text, mode, *, min_length=5, configs=None):
    """Tokens for one filter mode, newest first and without duplicates, as the picker lists them."""
    if mode == "line":
        res = get_lines(text, min_length=min_length)
    elif mode == "all":
        extrakto = Extrakto(min_length=min_length, alt=True, prefix_name=True, configs=configs)
        res = [item for name in extrakto.all() for item in extrakto[name].filter(text)]
    else:
        res = Extrakto(min_length=min_length, configs=configs)[mode].filter(text)
    res.reverse()
    return list(OrderedDict.fromkeys(res))


def extract_main(argv):
    parser = argparse.ArgumentParser(prog="rextracto.py extract", description="Extracts tokens from plaintext.")
    parser.add_argument("--name", action="store_true", help="prefix filter name in the output")
    parser.add_argument("-w", "--words", action="store_true", help='extract "word" tokens')
    parser.add_argument("-l", "--lines", action="store_true", help="extract lines")
    parser.add_argument("--all", action="store_true", help="extract using all filters defined in extrakto.conf")
    parser.add_argument("-a", "--add", action="append", default=[], help="add custom filter")
    parser.add_argument("-p", "--paths", action="store_true", help="short for -a=path")
    parser.add_argument("-u", "--urls", action="store_true", help="short for -a=url")
    parser.add_argument("--alt", action="store_true", help="return alternate variants for each match")
    parser.add_argument("-r", "--reverse", action="store_true", help="reverse output")
    parser.add_argument("-m", "--min-length", default=5, type=int, help="minimum token length")
    parser.add_argument("--warn-empty", action="store_true", help="warn if result is empty")
    args = parser.parse_args(argv)

    run_list = (["word"] if args.words else []) + (["path"] if args.paths else []) + (["url"] if args.urls else [])
    run_list += args.add
    # input from the terminal can cause UnicodeDecodeErrors in some instances, ignore for now
    text = sys.stdin.buffer.read().decode("utf-8", "ignore")
    extrakto = Extrakto(min_length=args.min_length, alt=args.alt, prefix_name=args.name)
    if args.all:
        run_list = extrakto.all()
    res = get_lines(text, min_length=args.min_length, prefix_name=args.name) if args.lines else []
    for name in run_list:
        res += extrakto[name].filter(text)
    if res:
        if args.reverse:
            res.reverse()
        for item in OrderedDict.fromkeys(res):
            print(item)
    elif args.warn_empty:
        print("NO MATCH - use a different filter")
    return 0


# Rex


def rex(*args):
    result = subprocess.run(
        [REX, "--autostart=false", "--timeout", TIMEOUT, *args],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"rex {args[0]} failed")
    return json.loads(result.stdout or "null")


def api(method, **params):
    return rex("api", "call", method, json.dumps(params)) or {}


def block_call(session, block, method, params=None):
    return rex("block", "call", "-s", session, "-b", block, method, json.dumps(params or {})) or {}


def window_blocks(session, block):
    """Terminal blocks tiled in BLOCK's window, BLOCK last."""
    for window in api("session.view", session_id=session).get("windows") or []:
        layers = window.get("layers") or []
        blocks = [entry for layer in layers for entry in layer.get("blocks") or []]
        if any(entry.get("block_id") == block for entry in blocks):
            tiled = [entry for layer in layers if layer.get("kind") == "tiled" for entry in layer.get("blocks") or []]
            others = [
                entry["block_id"]
                for entry in tiled
                if entry.get("block_id") != block
                and str(entry.get("flavor", "")).startswith("com.superlogical.terminal")
            ]
            return others + [block]
    return [block]


def grab_area_type(value):
    if not GRAB_AREA.fullmatch(value):
        raise argparse.ArgumentTypeError(
            f"{value!r} is not recent, full, a line count, or one of those after 'window '"
        )
    return value


def history_lines(grab_area):
    """Lines of history to take besides the screen, or None for all of it; a number is a line count, as in extrakto."""
    size = grab_area.split()[-1]
    return None if size == "full" else RECENT_LINES if size == "recent" else int(size)


def capture_block(session, block, history):
    content = block_call(session, block, "format", {"unwrap": True, "trim": True}).get("content", "")
    if history is None:
        return content
    rows = block_call(session, block, "size").get("rows") or 0
    # Unwrapped lines can be fewer than screen rows; this keeps at least the screen and HISTORY more.
    return "\n".join(content.rstrip("\n").split("\n")[-(rows + history) :])


def capture(session, block, grab_area):
    blocks = window_blocks(session, block) if grab_area.startswith("window ") else [block]
    return "\n".join(capture_block(session, entry, history_lines(grab_area)) for entry in blocks)


def next_grab_area(area, single_pane, original):
    """extrakto's grab key: recent, window recent, full, window full, then back to a custom starting area."""
    restart = original if original not in GRAB_AREAS else "recent"
    if area == "recent":
        return "full" if single_pane else "window recent"
    if area == "window recent":
        return "full"
    if area == "full":
        return restart if single_pane else "window full"
    if area == "window full":
        return restart
    return "recent"


OSC52_SETTLE = 0.1


def run_clipboard(command, text, shell=False):
    # wl-copy and xclip stay alive to serve the selection; their own session keeps the pane's hangup from killing them.
    subprocess.run(command, shell=shell, input=text, text=True, check=False, start_new_session=True)


def copy_text(text, clip_tool=None):
    if clip_tool:
        run_clipboard(clip_tool, text, shell=True)
        return
    for tool in (
        ["pbcopy"],
        ["wl-copy"] if os.environ.get("WAYLAND_DISPLAY") else None,
        ["xclip", "-selection", "clipboard"] if os.environ.get("DISPLAY") else None,
    ):
        if tool and shutil.which(tool[0]):
            run_clipboard(tool, text)
            return
    with open("/dev/tty", "w") as tty_out:
        tty_out.write("\x1b]52;c;" + base64.b64encode(text.encode()).decode() + "\a")
        tty_out.flush()
    # The pane closes when this script exits; give Rex a moment to read the sequence first.
    time.sleep(OSC52_SETTLE)


def block_cwd(session, block):
    try:
        process = block_call(session, block, "process")
        return (process.get("foreground") or {}).get("cwd") or block_call(session, block, "pwd").get("path")
    except RuntimeError:
        return None


def open_entries(entries, open_tool, cwd):
    """Open each entry on its own (xdg-open takes one argument), expanding ~ as a shell would."""
    command = shlex.split(open_tool) if open_tool else ["open" if sys.platform == "darwin" else "xdg-open"]
    for entry in entries:
        subprocess.Popen(
            [*command, os.path.expanduser(entry)],
            cwd=cwd if cwd and os.path.isdir(cwd) else None,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


# Picker

BOLD, YELLOW, OFF = "\x1b[1m", "\x1b[0;33m", "\x1b[0m"


def header(options, mode, grab_area):
    def key(name):
        return BOLD + getattr(options, name).replace("ctrl-", "^") + OFF

    parts = [
        f"{key('insert_key')}=insert",
        f"{key('copy_key')}=copy",
        f"{key('open_key')}=open",
        f"{key('edit_key')}=edit",
        f"{key('filter_key')}=filter [{YELLOW}{BOLD}{mode}{OFF}]",
        f"{key('grab_key')}=grab [{YELLOW}{BOLD}{grab_area}{OFF}]",
        f"{key('help_key')}=help",
    ]
    return ", ".join(parts)


def run_fzf(options, items, query, mode, grab_area):
    keys = [
        options.insert_key,
        options.copy_key,
        options.filter_key,
        options.edit_key,
        options.open_key,
        options.grab_key,
        options.help_key,
        "ctrl-c",
        "esc",
    ]
    env = dict(os.environ)
    if options.fzf_unset_default_opts:
        env.pop("FZF_DEFAULT_OPTS", None)
    command = shlex.split(options.fzf_tool) + [
        "--multi",
        "--print-query",
        f"--query={query}",
        f"--header={header(options, mode, grab_area)}",
        f"--expect={','.join(keys)}",
        "--tiebreak=index",
        f"--layout={options.fzf_layout}",
        "--no-info",
        "--ansi",
    ]
    result = subprocess.run(command, input="\n".join(items) + "\n", stdout=subprocess.PIPE, text=True, env=env)
    lines = result.stdout.split("\n")
    if result.returncode not in (0, 1, 130) or len(lines) < 2:
        raise RuntimeError(f"fzf failed with status {result.returncode}")
    return lines[0], lines[1], [line for line in lines[2:] if line]


def selection_entries(mode, selection):
    """The selected entries, without the filter labels that the all mode shows."""
    return [entry.split(": ", 1)[-1] for entry in selection] if mode == "all" else list(selection)


def selection_text(mode, selection):
    return ("\n" if mode == "line" else " ").join(selection_entries(mode, selection))


def filter_modes(filter_order, configs=None):
    """The filters Ctrl-F cycles through, checked before fzf opens."""
    modes = filter_order.split()
    if not modes:
        raise ExtraktoException("filter_order is empty; give it filter names such as 'word all line'")
    known = {"all", "line", *Extrakto(configs=configs).keys()}
    unknown = [mode for mode in modes if mode not in known]
    if unknown:
        raise ExtraktoException(
            f"unknown filter in filter_order: {', '.join(unknown)} (known: {' '.join(sorted(known))})"
        )
    return modes


def pick(options):
    session, block = options.session, options.block
    modes = filter_modes(options.filter_order)
    mode, grab_area, query = modes[0], options.grab_area, ""
    single_pane = len(window_blocks(session, block)) == 1
    if single_pane and grab_area.startswith("window "):
        grab_area = grab_area[len("window ") :]
    original_grab_area = grab_area
    while True:
        text = capture(session, block, grab_area)
        items = extract(text, mode, min_length=options.min_length)
        query, key, selection = run_fzf(options, items or ["NO MATCH - use a different filter"], query, mode, grab_area)
        value = selection_text(mode, selection) if items else ""
        if key == options.filter_key:
            mode = modes[(modes.index(mode) + 1) % len(modes)]
        elif key == options.grab_key:
            grab_area = next_grab_area(grab_area, single_pane, original_grab_area)
        elif key == options.help_key:
            subprocess.run(
                ["less", "-+EF", "-R"],
                input=HELP.format(recent=RECENT_LINES, filters=" ".join(modes), **vars(options)),
                text=True,
            )
        elif not value or key in ("esc", "ctrl-c", ""):
            return 0
        elif key == options.copy_key:
            copy_text(value, options.clip_tool)
            return 0
        elif key == options.insert_key:
            api("block.event", session_id=session, block_id=block, event={"type": "paste", "payload": {"text": value}})
            return 0
        elif key == options.open_key:
            open_entries(selection_entries(mode, selection), options.open_tool, block_cwd(session, block))
            return 0
        elif key == options.edit_key:
            editor = options.editor or os.environ.get("EDITOR") or "vi"
            words = " ".join(shell_word(entry) for entry in selection_entries(mode, selection))
            block_call(session, block, "write", {"data": f"{editor} -- {words}\r"})
            return 0
        else:
            return 0


def shell_word(entry):
    """ENTRY quoted for the pane's shell, leaving a leading ~/ outside the quotes so the shell expands it."""
    if entry == "~":
        return entry
    if entry.startswith("~/"):
        return "~/" + shlex.quote(entry[2:]) if entry[2:] else "~/"
    return shlex.quote(entry)


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("session")
    parser.add_argument("block")
    parser.add_argument("--grab-area", default="window full", type=grab_area_type, metavar="AREA")
    parser.add_argument("--filter-order", default="word all line", help="filters ctrl-f cycles through")
    parser.add_argument("--min-length", default=5, type=int)
    parser.add_argument(
        "--clip-tool", help="shell command that copies stdin (default: pbcopy, wl-copy, xclip or OSC 52)"
    )
    parser.add_argument("--open-tool", help="opener command (default: open or xdg-open)")
    parser.add_argument("--editor", help="editor for the edit key (default: $EDITOR)")
    parser.add_argument("--fzf-tool", default="fzf")
    parser.add_argument("--fzf-layout", default="default")
    parser.add_argument(
        "--fzf-unset-default-opts", default=True, type=lambda value: value.lower() in ("1", "true", "yes", "on")
    )
    for name, default in (
        ("insert", "tab"),
        ("copy", "enter"),
        ("filter", "ctrl-f"),
        ("open", "ctrl-o"),
        ("edit", "ctrl-e"),
        ("grab", "ctrl-g"),
        ("help", "ctrl-h"),
    ):
        parser.add_argument(f"--{name}-key", default=default)
    return parser.parse_args(argv)


def main(argv):
    if argv[:1] == ["extract"]:
        return extract_main(argv[1:])
    return pick(parse_args(argv))


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (ExtraktoException, OSError, RuntimeError, subprocess.SubprocessError, ValueError) as exc:
        print(f"rextracto: {exc}", file=sys.stderr)
        time.sleep(2)
        sys.exit(1)
