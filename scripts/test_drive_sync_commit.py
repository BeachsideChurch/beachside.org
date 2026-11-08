"""Verify descriptions match staged files, including multi-message syncs."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from build_drive_sync_commit import build_message


class CommitMessageTests(unittest.TestCase):
    def test_staged_message_names_and_changed_file_types(self):
        original = Path.cwd()
        with tempfile.TemporaryDirectory() as temp:
            try:
                os.chdir(temp)
                subprocess.run(["git", "init", "--quiet"], check=True)
                watch = Path("content/messages/chill/Watch - Week 2.md")
                guide = Path("content/discipleship-guide/Guide - Week 2.md")
                document = "---\ntitle: Just a Chill Guy - Part 2\ndate: 2026-11-01\n---\n"
                for path in (watch, guide):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(document, encoding="utf-8")
                subprocess.run(["git", "add", "."], check=True)
                watch.write_text(document.replace("Part 2", "Unstaged title"), encoding="utf-8")
                message = build_message()
                self.assertEqual(message.splitlines()[0],
                    "Sync 2026-11-01 Just a Chill Guy - Part 2 (Guide, Watch)")
                self.assertEqual(message.count("- 2026-11-01 Just a Chill Guy - Part 2"), 1)
                self.assertIn(f"Added Watch: {watch.as_posix()}", message)
                self.assertIn(f"Added Guide: {guide.as_posix()}", message)
                self.assertNotIn("Unstaged title", message)
                later = watch.parent / "Watch - Week 3.md"
                later.write_text(document.replace("Part 2", "Part 3").replace("11-01", "11-08"))
                subprocess.run(["git", "add", "--", str(later)], check=True)
                self.assertIn("(+1 more)", build_message().splitlines()[0])
                self.assertIn("2026-11-08 Just a Chill Guy - Part 3", build_message())
            finally:
                os.chdir(original)


if __name__ == "__main__":
    unittest.main()
