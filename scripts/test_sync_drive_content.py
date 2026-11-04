"""Offline checks: no Drive or GitHub requests, no production content writes."""

from pathlib import Path
from datetime import datetime, timedelta, timezone
import tempfile
import unittest

from sync_drive_content import FOLDER, apply_plan, frontmatter, plan_sync


WATCH = b'''---
title: Just a Chill Guy - Part 2
series: Just a Chill Guy
date: 2026-11-01
image: /images/messages/chillguy.jpg
guide_url: /discipleship-guide/chillguy-pt2/
draft: false
---
'''
GUIDE = b'''---
title: Just a Chill Guy - Part 2
series: Just a Chill Guy
date: 2026-11-01
slug: chillguy-pt2
---
Guide body with two trailing spaces.  
'''


def item(id, name, mime="text/markdown"):
    return dict(id=id, name=name, mimeType=mime,
                createdTime=datetime.now(timezone.utc).isoformat())


class FakeDrive:
    def __init__(self):
        self.folders = {
            "root": [item("week", "2026-11-01 Just a Chill Guy P2", FOLDER)],
            "week": [item("watch", "Watch - 2026-11-01 Just a Chill Guy P2.md"),
                     item("guide", "Guide - 2026-11-01 Just a Chill Guy P2.md"),
                     item("image", "chillguy.jpg", "image/jpeg"),
                     item("transcript", "Clean Transcript", "application/vnd.google-apps.document")],
        }
        self.data = {"watch": WATCH, "guide": GUIDE, "image": b"\xff\xd8\xfftest-jpeg"}

    def children(self, id):
        return self.folders[id]

    def metadata(self, id):
        for items in self.folders.values():
            for entry in items:
                if entry["id"] == id:
                    return entry
        return item(id, "Source folder", FOLDER)

    def download(self, item):
        return self.data[item["id"]]


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.drive = FakeDrive()

    def test_routing_preserves_bytes_and_repeated_runs_are_unchanged(self):
        plan = plan_sync(self.drive, "root", self.root)
        self.assertEqual(len(plan), 4)  # Includes new series landing page.
        self.assertEqual(len(apply_plan(plan, self.root, dry_run=True)), 4)
        self.assertEqual(list(self.root.iterdir()), [])
        apply_plan(plan, self.root)
        self.assertEqual((self.root / "content/discipleship-guide/Guide - 2026-11-01 Just a Chill Guy P2.md").read_bytes(), GUIDE)
        self.assertEqual((self.root / "static/images/messages/chillguy.jpg").read_bytes(), self.drive.data["image"])
        self.assertEqual(apply_plan(plan_sync(self.drive, "root", self.root), self.root), [])

    def test_existing_series_directory_is_preserved(self):
        directory = self.root / "content/messages/Just A Chill Guy"
        directory.mkdir(parents=True)
        index = directory / "_index.md"
        original = WATCH.replace(b"series: Just a Chill Guy", b"series: Just A Chill Guy")
        index.write_bytes(original)
        plan = plan_sync(self.drive, "week", self.root)
        self.assertIn(directory / "Watch - 2026-11-01 Just a Chill Guy P2.md", plan)
        self.assertIn(index, plan)
        self.assertEqual(str(frontmatter(plan[index])["lastmod"]), "2026-11-01")
        self.assertEqual(plan[index].replace(b'\nlastmod: "2026-11-01"', b''), original)
        self.assertEqual(index.read_bytes(), original)

    def test_multiple_parts_create_one_index_with_first_date_and_latest_lastmod(self):
        self.drive.folders["root"].append(item("earlier", "Z earlier message", FOLDER))
        self.drive.folders["earlier"] = [
            item("watch1", "Watch - Part 1.md"), item("guide1", "Guide - Part 1.md"),
            item("image", "chillguy.jpg", "image/jpeg")]
        self.drive.data["watch1"] = WATCH.replace(b"2026-11-01", b"2026-10-25").replace(b"Part 2", b"Part 1").replace(b"pt2", b"pt1")
        self.drive.data["guide1"] = GUIDE.replace(b"2026-11-01", b"2026-10-25").replace(b"Part 2", b"Part 1").replace(b"pt2", b"pt1")
        plan = plan_sync(self.drive, "root", self.root)
        directory = self.root / "content/messages/just-a-chill-guy"
        data = frontmatter(plan[directory / "_index.md"])
        self.assertEqual(str(data["date"]), "2026-10-25")
        self.assertEqual(str(data["lastmod"]), "2026-11-01")
        self.assertEqual(len([p for p in plan if p.parent == directory]), 3)

    def test_existing_index_preserves_content_and_old_sync_does_not_regress_lastmod(self):
        directory = self.root / "content/messages/just-a-chill-guy"
        directory.mkdir(parents=True)
        index = directory / "_index.md"
        original = WATCH.replace(b"---\n", b"---\nlastmod: '2026-10-25' # keep comment\n", 1) + b"Series introduction.\n"
        index.write_bytes(original)
        # A later message already in GitHub also contributes to lastmod.
        (directory / "later.md").write_bytes(WATCH.replace(b"2026-11-01", b"2026-11-08"))
        plan = plan_sync(self.drive, "week", self.root)
        updated = plan[index]
        self.assertEqual(updated, original.replace(b"'2026-10-25'", b'"2026-11-08"'))
        apply_plan(plan, self.root)
        self.assertNotIn(index, plan_sync(self.drive, "week", self.root))

    def test_incomplete_upload_fails_without_writing(self):
        self.drive.folders["week"].pop(1)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            plan_sync(self.drive, "root", self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_broken_links_and_non_jpeg_are_rejected(self):
        for key, raw, message in [
            ("watch", WATCH.replace(b"chillguy-pt2", b"wrong-guide"), "guide_url"),
            ("watch", WATCH.replace(b"chillguy.jpg", b"wrong.jpg"), "image must reference"),
            ("image", b"not a JPEG", "not a JPEG"),
            ("guide", GUIDE.replace(b"2026-11-01", b"2026-11-02"), "date/series"),
        ]:
            with self.subTest(message=message):
                drive = FakeDrive()
                drive.data[key] = raw
                with self.assertRaisesRegex(ValueError, message):
                    plan_sync(drive, "root", self.root)

    def test_conflicting_duplicate_destinations_are_rejected(self):
        self.drive.folders["root"].append(item("other", "Another week", FOLDER))
        self.drive.folders["other"] = [dict(i) for i in self.drive.folders["week"]]
        self.drive.folders["other"][2]["id"] = "other-image"
        self.drive.data["other-image"] = b"\xff\xd8\xffdifferent-jpeg"
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            plan_sync(self.drive, "root", self.root)

    def test_unsafe_filename_is_rejected(self):
        self.drive.folders["week"][0]["name"] = "Watch - ../../outside.md"
        with self.assertRaisesRegex(ValueError, "Unsafe filename"):
            plan_sync(self.drive, "root", self.root)

    def test_creation_window_includes_boundary_and_skips_older_and_future(self):
        now = datetime(2026, 11, 3, 18, tzinfo=timezone.utc)
        for age, expected in [(timedelta(days=7), 4),
                              (timedelta(days=7, microseconds=1), 0),
                              (timedelta(days=1), 4),
                              (timedelta(seconds=-1), 0)]:
            with self.subTest(age=age):
                self.drive.folders["root"][0]["createdTime"] = (now - age).isoformat()
                self.assertEqual(len(plan_sync(self.drive, "root", self.root, now=now)), expected)

    def test_old_parent_is_traversed_and_old_incomplete_message_is_ignored(self):
        now = datetime.now(timezone.utc)
        old = item("old", "Old incomplete week", FOLDER)
        old["createdTime"] = (now - timedelta(days=30)).isoformat()
        self.drive.folders["old"] = [item("bad-watch", "Watch - incomplete.md")]
        parent = item("year", "Old year folder", FOLDER)
        parent["createdTime"] = old["createdTime"]
        self.drive.folders["year"] = self.drive.folders["root"] + [old]
        self.drive.folders["root"] = [parent]
        self.assertEqual(len(plan_sync(self.drive, "root", self.root)), 4)

    def test_direct_weekly_source_respects_window_and_all_folders_override(self):
        self.drive.folders["root"][0]["createdTime"] = "2020-01-01T00:00:00Z"
        self.assertEqual(plan_sync(self.drive, "week", self.root), {})
        self.assertEqual(len(plan_sync(self.drive, "week", self.root, all_folders=True)), 4)

    def test_edit_does_not_make_old_folder_eligible(self):
        self.drive.folders["root"][0].update(
            createdTime="2020-01-01T00:00:00Z",
            modifiedTime=datetime.now(timezone.utc).isoformat())
        self.drive.data["watch"] += b"An edited message.\n"
        self.assertEqual(plan_sync(self.drive, "root", self.root), {})


if __name__ == "__main__":
    unittest.main()
