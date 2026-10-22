import os
import subprocess
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", ".github", "scripts", "next-version.sh")


class NextVersionTests(unittest.TestCase):
    """The release workflow's version bump (#9)."""

    def setUp(self):
        self.repo = tempfile.TemporaryDirectory()
        self.addCleanup(self.repo.cleanup)
        self.git("init", "-q", "-b", "main")

    def git(self, *args):
        env = dict(
            os.environ,
            GIT_AUTHOR_NAME="Test",
            GIT_AUTHOR_EMAIL="test@example.com",
            GIT_COMMITTER_NAME="Test",
            GIT_COMMITTER_EMAIL="test@example.com",
        )
        subprocess.run(["git", *args], cwd=self.repo.name, env=env, check=True, capture_output=True)

    def commit(self, *messages):
        for message in messages:
            self.git("commit", "-q", "--allow-empty", "-m", message)

    def next_version(self):
        return subprocess.run(
            ["bash", SCRIPT], cwd=self.repo.name, check=True, capture_output=True, text=True
        ).stdout.strip()

    def test_first_release(self):
        self.commit("feat: first", "docs: readme")
        self.assertEqual(self.next_version(), "0.1.0")

    def test_patch_minor_and_nothing(self):
        self.commit("feat: first")
        self.git("tag", "v0.1.0")
        self.commit("docs: readme", "ci: workflow")
        self.assertEqual(self.next_version(), "")
        self.commit("fix(ui): bug")
        self.assertEqual(self.next_version(), "0.1.1")
        self.commit("feat: more")
        self.assertEqual(self.next_version(), "0.2.0")

    def test_breaking_before_one_bumps_minor(self):
        self.commit("feat: first")
        self.git("tag", "v0.3.2")
        self.commit("feat!: change everything")
        self.assertEqual(self.next_version(), "0.4.0")

    def test_breaking_after_one_bumps_major(self):
        self.commit("feat: first")
        self.git("tag", "v1.4.2")
        self.commit("fix: small", "refactor: x\n\nBREAKING CHANGE: options renamed")
        self.assertEqual(self.next_version(), "2.0.0")

    def test_breaking_footer_in_long_history(self):
        self.commit("feat: first")
        self.git("tag", "v1.0.0")
        self.commit("refactor: y\n\nBREAKING CHANGE: gone")
        for index in range(40):  # over 64 KB of log, more than a pipe buffer
            self.commit(f"fix: number {index}\n\n" + "body line\n" * 200)
        self.assertEqual(self.next_version(), "2.0.0")

    def test_prerelease_tags_are_ignored(self):
        self.commit("feat: first")
        self.git("tag", "v0.2.0")
        self.commit("fix: one")
        self.git("tag", "v0.2.1-rc1")
        self.assertEqual(self.next_version(), "0.2.1")


if __name__ == "__main__":
    unittest.main()
