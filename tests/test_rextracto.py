import os
import subprocess
import sys
import unittest
from unittest import mock

TESTS = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(TESTS)
sys.path.insert(0, ROOT)

import rextracto as extrakto  # noqa: E402

DEFAULT_CONF = [os.path.join(ROOT, "rextracto.conf")]


def run_filter(name, text):
    return extrakto.Extrakto(configs=DEFAULT_CONF)[name].filter(text)


class AssetTests(unittest.TestCase):
    """Same fixtures and expected output as upstream extrakto's test_assets.py."""

    def check(self, switch, name):
        with open(os.path.join(TESTS, "assets", f"{name}.txt"), "rb") as source:
            result = subprocess.run(
                [sys.executable, os.path.join(ROOT, "rextracto.py"), "extract", switch, "--alt"],
                stdin=source,
                capture_output=True,
                check=True,
                env=dict(os.environ, HOME=TESTS),  # ignore the user's own filter config
            )
        with open(os.path.join(TESTS, "assets", f"{name}_result{switch}.txt"), "rb") as expected:
            self.assertEqual(result.stdout.decode(), expected.read().decode(), f"{name} {switch}")

    def test_assets(self):
        for name in ["text2", "path", "unicode", "quotes"]:
            self.check("-w", name)
        self.check("-pu", "path")
        self.check("-a=quote", "quotes")


class FilterTests(unittest.TestCase):
    def test_urls(self):
        for url in [
            "http://example.com",
            "https://example.com/a?b=1",
            "ftp://files.example.com",
            "sftp://files.example.com",
            "file:////home/user",
            "git@example.com:user/repo.git",
            "HTTP://EXAMPLE.COM",
        ]:
            self.assertEqual(run_filter("url", f"hey, open {url} etc..."), [url])

    def test_paths(self):
        self.assertEqual(run_filter("path", "hey, test ~/tmp/test.txt etc..."), ["~/tmp/test.txt"])
        self.assertEqual(run_filter("path", "open this file /home/user/test.txt etc..."), ["/home/user/test.txt"])
        self.assertEqual(run_filter("path", "5k/s and page 1/2"), [])

    def test_words(self):
        self.assertEqual(run_filter("word", "a (short) [example] with=equals"), ["short", "example", "equals"])

    def test_lines(self):
        self.assertEqual(extrakto.get_lines("  first line  \nno\n\nsecond line"), ["first line", "second line"])


class ExtractTests(unittest.TestCase):
    text = "run /tmp/one.txt\nthen https://example.com/x\nand /tmp/one.txt again"

    def test_newest_first_unique(self):
        self.assertEqual(extrakto.extract(self.text, "path", configs=DEFAULT_CONF), ["/tmp/one.txt"])
        self.assertEqual(
            extrakto.extract(self.text, "line", configs=DEFAULT_CONF),
            ["and /tmp/one.txt again", "then https://example.com/x", "run /tmp/one.txt"],
        )

    def test_all_prefixes_names(self):
        items = extrakto.extract(self.text, "all", configs=DEFAULT_CONF)
        self.assertIn("url: https://example.com/x", items)
        self.assertIn("url2: example.com", items)
        self.assertIn("path: /tmp/one.txt", items)

    def test_selection_text(self):
        self.assertEqual(
            extrakto.selection_text("all", ["url: https://x.example", "path: /tmp/a b"]), "https://x.example /tmp/a b"
        )
        self.assertEqual(extrakto.selection_text("line", ["one", "two"]), "one\ntwo")
        self.assertEqual(extrakto.selection_text("word", ["one", "two"]), "one two")


class GrabAreaTests(unittest.TestCase):
    def test_cycle(self):
        self.assertEqual(extrakto.next_grab_area("recent", False), "full")
        self.assertEqual(extrakto.next_grab_area("window full", False), "recent")
        self.assertEqual(extrakto.next_grab_area("full", True), "recent")
        self.assertEqual(extrakto.next_grab_area("window full", True), "recent")


VIEW = {
    "windows": [
        {
            "layers": [
                {
                    "kind": "tiled",
                    "blocks": [{"block_id": "block:other-window", "flavor": "com.superlogical.terminal.shell"}],
                }
            ]
        },
        {
            "layers": [
                {
                    "kind": "tiled",
                    "blocks": [
                        {"block_id": "block:left", "flavor": "com.superlogical.terminal.shell"},
                        {"block_id": "block:b", "flavor": "com.superlogical.terminal.shell"},
                        {"block_id": "block:web", "flavor": "com.example.browser"},
                    ],
                },
                {
                    "kind": "floating",
                    "blocks": [{"block_id": "block:picker", "flavor": "com.superlogical.terminal.shell"}],
                },
            ]
        },
    ]
}


class CaptureTests(unittest.TestCase):
    def test_window_blocks(self):
        with mock.patch.object(extrakto, "api", return_value=VIEW):
            self.assertEqual(extrakto.window_blocks("session:a", "block:b"), ["block:left", "block:b"])
            self.assertEqual(extrakto.window_blocks("session:a", "block:missing"), ["block:missing"])

    def test_recent_keeps_screen_and_history(self):
        content = "\n".join(f"line {index}" for index in range(100)) + "\n"

        def block_call(session, block, method, params=None):
            return {"content": content} if method == "format" else {"rows": 5}

        with mock.patch.object(extrakto, "block_call", side_effect=block_call):
            recent = extrakto.capture_block("session:a", "block:b", True).split("\n")
            self.assertEqual(recent[0], "line 85")
            self.assertEqual(recent[-1], "line 99")
            self.assertEqual(extrakto.capture_block("session:a", "block:b", False), content)

    def test_window_capture_puts_target_last(self):
        with (
            mock.patch.object(extrakto, "window_blocks", return_value=["block:left", "block:b"]),
            mock.patch.object(extrakto, "capture_block", side_effect=lambda s, block, recent: f"{block} {recent}"),
        ):
            self.assertEqual(extrakto.capture("session:a", "block:b", "window recent"), "block:left True\nblock:b True")
            self.assertEqual(extrakto.capture("session:a", "block:b", "full"), "block:b False")


class PickTests(unittest.TestCase):
    text = "see https://example.com/x and /tmp/notes.txt"

    def setUp(self):
        self.calls, self.fzf = [], []
        patches = [
            mock.patch.object(extrakto, "window_blocks", return_value=["block:left", "block:b"]),
            mock.patch.object(
                extrakto, "capture", side_effect=lambda s, b, area: self.calls.append(("capture", area)) or self.text
            ),
            mock.patch.object(
                extrakto, "api", side_effect=lambda method, **params: self.calls.append((method, params))
            ),
            mock.patch.object(
                extrakto, "block_call", side_effect=lambda *args: self.calls.append(("block_call",) + args)
            ),
            mock.patch.object(extrakto, "copy_text", side_effect=lambda *args: self.calls.append(("copy",) + args)),
            mock.patch.object(extrakto, "open_entries", side_effect=lambda *args: self.calls.append(("open",) + args)),
            mock.patch.object(extrakto, "block_cwd", return_value="/tmp"),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def pick(self, answers, *argv):
        answers = list(answers)

        def run_fzf(options, items, query, mode, grab_area):
            self.fzf.append((mode, grab_area, items))
            key, selection = answers.pop(0)
            return query, key, selection

        with mock.patch.object(extrakto, "run_fzf", side_effect=run_fzf):
            return extrakto.pick(extrakto.parse_args([*argv, "session:a", "block:b"]))

    def test_copy(self):
        self.pick([("enter", ["/tmp/notes.txt"])], "--clip-tool", "cat")
        self.assertEqual(self.calls[-1], ("copy", "/tmp/notes.txt", "cat"))

    def test_insert_pastes_into_pane(self):
        self.pick([("tab", ["one", "two"])])
        self.assertEqual(
            self.calls[-1],
            (
                "block.event",
                {
                    "session_id": "session:a",
                    "block_id": "block:b",
                    "event": {"type": "paste", "payload": {"text": "one two"}},
                },
            ),
        )

    def test_filter_and_grab_cycle(self):
        self.pick([("ctrl-f", []), ("ctrl-g", []), ("esc", [])])
        self.assertEqual(
            [(mode, area) for mode, area, _ in self.fzf],
            [("word", "window full"), ("all", "window full"), ("all", "recent")],
        )
        self.assertIn("url: https://example.com/x", self.fzf[1][2])

    def test_single_pane_skips_window_areas(self):
        with mock.patch.object(extrakto, "window_blocks", return_value=["block:b"]):
            self.pick([("ctrl-g", []), ("esc", [])])
        self.assertEqual([area for _, area, _ in self.fzf], ["full", "recent"])

    def test_edit_types_editor_command(self):
        self.pick([("ctrl-e", ["/tmp/a b.txt"])], "--editor", "nvim")
        self.assertEqual(
            self.calls[-1], ("block_call", "session:a", "block:b", "write", {"data": "nvim -- '/tmp/a b.txt'\r"})
        )

    def test_open_uses_pane_directory(self):
        self.pick([("ctrl-o", ["https://example.com/x"])])
        self.assertEqual(self.calls[-1], ("open", ["https://example.com/x"], None, "/tmp"))

    def test_all_mode_strips_names(self):
        self.pick([("ctrl-f", []), ("enter", ["url: https://example.com/x"])])
        self.assertEqual(self.calls[-1][:2], ("copy", "https://example.com/x"))

    def test_no_match_is_not_selectable(self):
        self.text = "a b"
        self.pick([("enter", ["NO MATCH - use a different filter"])])
        self.assertEqual(self.fzf[0][2], ["NO MATCH - use a different filter"])
        self.assertFalse([call for call in self.calls if call[0] == "copy"])

    def test_custom_keys(self):
        self.pick([("ctrl-y", ["/tmp/notes.txt"])], "--copy-key", "ctrl-y")
        self.assertEqual(self.calls[-1][:2], ("copy", "/tmp/notes.txt"))


if __name__ == "__main__":
    unittest.main()
