"""Describe the staged Drive sync changes in a Git commit message."""

import argparse
from pathlib import Path, PurePosixPath
import re
import subprocess

import yaml


def git(*args):
    return subprocess.check_output(["git", *args])


def describe_file(path):
    parts = PurePosixPath(path).parts
    if parts[:2] == ("content", "discipleship-guide"):
        return "Guide"
    if parts[:2] == ("content", "messages"):
        return "Series index" if parts[-1] == "_index.md" else "Watch"
    return "Artwork"


def clean_line(value):
    return " ".join(str(value).split())


def build_message():
    fields = git("diff", "--cached", "--name-status", "--no-renames", "-z").split(b"\0")
    files = []
    messages = []
    kinds = []
    verbs = {"A": "Added", "M": "Updated", "D": "Deleted", "T": "Changed"}
    for offset in range(0, len(fields) - 1, 2):
        status = fields[offset].decode("ascii")
        path = fields[offset + 1].decode("utf-8")
        kind = describe_file(path)
        files.append(f"- {verbs.get(status, 'Changed')} {kind}: {path}")
        if kind not in kinds:
            kinds.append(kind)
        if kind not in ("Watch", "Guide") or status == "D":
            continue
        # Read staged content so unstaged edits cannot change the description.
        text = git("show", f":{path}").decode("utf-8-sig").replace("\r\n", "\n")
        header = re.match(r"\A---\n(.*?)\n---(?:\n|$)", text, re.S)
        data = yaml.safe_load(header.group(1)) if header else {}
        data = data or {}
        title = data.get("title") or PurePosixPath(path).stem
        label = clean_line(f"{data.get('date', '')} {title}")
        if label not in messages:
            messages.append(label)
    if not files:
        raise ValueError("No staged sync changes")
    subject = "Sync " + (messages[0] if messages else "message content")
    if len(messages) > 1:
        subject += f" (+{len(messages) - 1} more)"
    subject += " (" + ", ".join(kinds) + ")"
    body = ["Synced from Google Drive."]
    if messages:
        body.extend(["", "Messages:", *[f"- {label}" for label in messages]])
    body.extend(["", "Files:", *files])
    return subject + "\n\n" + "\n".join(body) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    Path(args.output).write_text(build_message(), encoding="utf-8")
