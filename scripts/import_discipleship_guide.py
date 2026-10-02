#!/usr/bin/env python3

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
import unicodedata

from content_yaml import dump_content


DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday"]


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug or "discipleship-guide"


def build_output_slug(title: str, series: str | None = None) -> str:
    title_slug = slugify(title)
    if not series:
        return title_slug
    series_slug = slugify(series)
    if not series_slug:
        return title_slug
    return f"{series_slug}--{title_slug}"


def parse_date(value: Any) -> str:
    if not value:
        return datetime.now().strftime("%Y-%m-%dT09:00:00-05:00")
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return datetime.now().strftime("%Y-%m-%dT09:00:00-05:00")
        if "T" in value or value.endswith("Z"):
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return dt.isoformat()
            except ValueError:
                pass
        try:
            dt = datetime.strptime(value, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%dT09:00:00-05:00")
        except ValueError:
            pass
    return datetime.now().strftime("%Y-%m-%dT09:00:00-05:00")


def render_doc(payload: dict[str, Any]) -> str:
    fields = payload.get("fields", {})
    title = str(payload.get("title") or fields.get("message_title") or "Untitled Guide").strip()
    devotions = fields.get("daily_devotions") or {}
    if isinstance(devotions, dict):
        devotions = [dict(day=day.title(), **devotions[day]) for day in DAY_ORDER if devotions.get(day)]
    data = {
        "title": title,
        "date": parse_date(fields.get("guide_date") or payload.get("date")),
        "guide_format": "structured",
        "speaker": fields.get("speaker") or "",
        "series": fields.get("series") or "",
        "display_series": bool(fields.get("display_series", False)),
        "description": fields.get("description") or fields.get("main_idea") or title,
        "draft": True,
        "video_url": fields.get("youtube_link") or "",
        "message_recap": fields.get("message_recap") or "",
        "main_idea": fields.get("main_idea") or "",
        "discussion_questions": fields.get("discussion_questions") or [],
        "daily_devotions": devotions,
        "spiritual_practice": fields.get("spiritual_practice") or "",
        "prayer_prompts": fields.get("prayer_prompts") or [],
        "next_steps": fields.get("next_steps") or [],
        "resources": fields.get("resources") or [],
    }
    return "---\n" + dump_content(data) + "---\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a discipleship guide JSON payload into a Hugo markdown file.")
    parser.add_argument("--input", required=True, help="Path to the JSON file, or '-' to read from stdin.")
    parser.add_argument("--output-dir", default="content/discipleship-guide", help="Directory where the generated file should be written.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing file if one already exists.")
    parser.add_argument("--stdout", action="store_true", help="Print the generated file to stdout instead of writing it to disk.")
    args = parser.parse_args()

    if args.input == "-":
        payload = json.load(sys.stdin)
    else:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Input file not found: {input_path}", file=sys.stderr)
            return 1
        with input_path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)

    rendered = render_doc(payload)
    title = str((payload.get("title") or payload.get("fields", {}).get("message_title") or "discipleship-guide")).strip()
    series = str((payload.get("series") or (payload.get("fields", {}) or {}).get("series") or "")).strip()
    slug = build_output_slug(title, series)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{slug}.md"

    if args.stdout:
        print(rendered)
        return 0

    if output_path.exists() and not args.force:
        print(f"File already exists: {output_path}. Use --force to overwrite it.", file=sys.stderr)
        return 1

    output_path.write_text(rendered, encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
