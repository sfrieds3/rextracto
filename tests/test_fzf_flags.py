import os
import shutil
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

import rextracto


class FzfFlagTests(unittest.TestCase):
    """Selections come back from fzf byte for byte (#7)."""

    def run_fzf_with(self, items, stdout):
        options = rextracto.parse_args(["session:a", "block:b"])
        result = subprocess.CompletedProcess([], 0, stdout=stdout)
        with mock.patch.object(rextracto.subprocess, "run", return_value=result) as run:
            answer = rextracto.run_fzf(options, items, "", "word", "full")
        return run.call_args.args[0], answer

    def test_no_ansi(self):
        command, _ = self.run_fzf_with(["a"], "\nenter\na\n")
        self.assertNotIn("--ansi", command)

    @unittest.skipUnless(shutil.which("fzf"), "fzf not installed")
    def test_escape_sequences_survive_fzf(self):
        # rextracto's own fzf command line, run non-interactively.
        item = "a\x1b[31mbcdef\x1b[0m"
        command, _ = self.run_fzf_with([item], "\nenter\n")
        result = subprocess.run([*command, "--filter", "bc"], input=item + "\n", capture_output=True, text=True)
        self.assertIn(item, result.stdout.split("\n"))


if __name__ == "__main__":
    unittest.main()
