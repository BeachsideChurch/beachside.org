"""One-way Drive -> Hugo sync, executed on a GitHub-hosted runner."""

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import unicodedata

import yaml

from content_yaml import dump_content

FOLDER = "application/vnd.google-apps.folder"
DOC = "application/vnd.google-apps.document"
API = "https://www.googleapis.com/drive/v3/files"


def slugify(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise ValueError("Series must have a usable name")
    return slug


def filename(value):
    if not value or value in {".", ".."} or any(c in value for c in '/\\:\x00\r\n'):
        raise ValueError(f"Unsafe filename: {value!r}")
    return value


def frontmatter(raw):
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    match = re.match(r"\A---\n(.*?)\n---(?:\n|$)", text, re.S)
    if not match:
        raise ValueError("Markdown must start with YAML front matter")
    data = yaml.safe_load(match.group(1))
    if not isinstance(data, dict):
        raise ValueError("Front matter must be a YAML mapping")
    for key in ("title", "date", "series"):
        if not data.get(key):
            raise ValueError(f"Missing front matter field: {key}")
    return data


def message_date(value):
    return date.fromisoformat(str(value)[:10])


def update_lastmod(raw, latest):
    """Replace only the YAML value, preserving other fields, comments and body."""
    text = raw.decode("utf-8")
    match = re.match(r"\A\ufeff?---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
    header = match.group(1)
    nodes = yaml.compose(header)
    for key, value in nodes.value:
        if key.value == "lastmod":
            start = match.start(1) + value.start_mark.index
            end = match.start(1) + value.end_mark.index
            return (text[:start] + f'"{latest.isoformat()}"' + text[end:]).encode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    end = match.end(1)
    return (text[:end] + newline + f'lastmod: "{latest.isoformat()}"' + text[end:]).encode("utf-8")


class Drive:
    def __init__(self, session):
        self.session = session

    def get(self, url, **params):
        response = self.session.get(url, params=params, timeout=90)
        response.raise_for_status()
        return response

    def children(self, folder_id):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", folder_id):
            raise ValueError("Provide a Drive folder ID, not its URL")
        token = None
        while True:
            page = self.get(
                API, q=f"'{folder_id}' in parents and trashed = false",
                fields="nextPageToken,incompleteSearch,files(id,name,mimeType,createdTime)",
                pageSize=1000, pageToken=token, supportsAllDrives="true",
                includeItemsFromAllDrives="true",
            ).json()
            if page.get("incompleteSearch"):
                raise ValueError("Drive returned an incomplete folder listing; sync aborted")
            yield from page.get("files", [])
            token = page.get("nextPageToken")
            if not token:
                break

    def metadata(self, folder_id):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", folder_id):
            raise ValueError("Provide a Drive folder ID, not its URL")
        return self.get(f"{API}/{folder_id}", fields="id,name,mimeType,createdTime",
                        supportsAllDrives="true").json()

    def download(self, item):
        if item["mimeType"] == DOC:
            raise ValueError(f"{item['name']}: upload an actual .md file, not a Google Doc")
        return self.get(f"{API}/{item['id']}", alt="media", supportsAllDrives="true").content


def plan_sync(drive, folder_id, root, *, now=None, all_folders=False):
    """Download and validate everything before allowing any repository writes."""
    plan = {}
    series_dirs = {}
    series_messages = {}
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)

    def eligible(folder):
        if all_folders:
            return True
        created = datetime.fromisoformat(folder["createdTime"].replace("Z", "+00:00"))
        if created.tzinfo is None:
            raise ValueError(f"Folder {folder['id']}: createdTime must include a timezone")
        return cutoff <= created <= now
    for index in sorted((root / "content/messages").glob("*/_index.md")):
        data = frontmatter(index.read_bytes())
        key = slugify(str(data["series"]))
        if key in series_dirs and series_dirs[key] != index.parent:
            raise ValueError(f"Ambiguous existing series: {data['series']}")
        series_dirs[key] = index.parent

    def add(path, raw):
        path = path.resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Destination escapes the repository")
        if path in plan and plan[path] != raw:
            raise ValueError(f"Conflicting Drive files target {path.relative_to(root)}")
        plan[path] = raw

    seen = set()

    def visit(folder):
        current = folder["id"]
        if current in seen:
            return
        seen.add(current)
        items = sorted(drive.children(current), key=lambda item: (item["name"], item["id"]))
        watches = [i for i in items if i["name"].startswith("Watch - ") and i["name"].endswith(".md")]
        guides = [i for i in items if i["name"].startswith("Guide - ") and i["name"].endswith(".md")]
        if (watches or guides) and eligible(folder):
            images = [i for i in items if i["name"].lower().endswith((".jpg", ".jpeg"))]
            if len(watches) != 1 or len(guides) != 1 or len(images) != 1:
                raise ValueError(f"Folder {current}: expected exactly one Watch .md, Guide .md and JPG")
            watch, guide, image = watches[0], guides[0], images[0]
            for item in (watch, guide, image):
                filename(item["name"])
            watch_raw, guide_raw, image_raw = [drive.download(i) for i in (watch, guide, image)]
            w, g = frontmatter(watch_raw), frontmatter(guide_raw)
            if str(w["date"]) != str(g["date"]) or slugify(str(w["series"])) != slugify(str(g["series"])):
                raise ValueError(f"{watch['name']}: Watch and Guide date/series must match")
            if w.get("image") != f"/images/messages/{image['name']}":
                raise ValueError(f"{watch['name']}: image must reference /images/messages/{image['name']}")
            # A guide slug makes the URL independent of its Drive filename.
            guide_slug = g.get("slug")
            if not isinstance(guide_slug, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", guide_slug):
                raise ValueError(f"{guide['name']}: set a lowercase, hyphenated slug")
            if str(w.get("guide_url", "")).rstrip("/") != f"/discipleship-guide/{guide_slug}":
                raise ValueError(f"{watch['name']}: guide_url does not match the Guide slug")
            if not image_raw.startswith(b"\xff\xd8\xff"):
                raise ValueError(f"{image['name']}: not a JPEG file")
            key = slugify(str(w["series"]))
            directory = series_dirs.get(key, root / "content/messages" / key)
            series_dirs[key] = directory
            series_messages.setdefault(key, []).append(w)
            add(directory / watch["name"], watch_raw)
            add(root / "content/discipleship-guide" / guide["name"], guide_raw)
            add(root / "static/images/messages" / image["name"], image_raw)
        for item in items:
            if item["mimeType"] == FOLDER:
                visit(item)

    source = drive.metadata(folder_id)
    if source["mimeType"] != FOLDER:
        raise ValueError("The sync source must be a Drive folder")
    visit(source)
    if not plan:
        print("No eligible message folders found; nothing to sync.")
        return plan
    for key, messages in series_messages.items():
        directory = series_dirs[key]
        index = directory / "_index.md"
        dates = [message_date(w["date"]) for w in messages]
        # Include messages already in GitHub, even when syncing only one old week.
        for path in directory.glob("*.md"):
            if path.name != "_index.md":
                data = frontmatter(plan.get(path.resolve(), path.read_bytes()))
                dates.append(message_date(data["date"]))
        if index.exists():
            raw = index.read_bytes()
            data = frontmatter(raw)
            dates.append(message_date(data["date"]))
            if data.get("lastmod"):
                dates.append(message_date(data["lastmod"]))
            latest = max(dates)
            if not data.get("lastmod") or message_date(data["lastmod"]) < latest:
                add(index, update_lastmod(raw, latest))
        else:
            first = min(messages, key=lambda w: message_date(w["date"]))
            data = {k: first[k] for k in ("series", "date", "image", "description", "draft") if k in first}
            data.update(title=first["series"], layout="series", lastmod=max(dates))
            add(index, ("---\n" + dump_content(data) + "---\n").encode())
    return plan


def apply_plan(plan, root, dry_run=False):
    changed = []
    for path, raw in sorted(plan.items()):
        if path.exists() and path.read_bytes() == raw:
            continue
        print(f"{'Would update' if dry_run else 'Updating'} {path.relative_to(root)}")
        changed.append(path)
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    print(f"{len(changed)} file(s) {'would change' if dry_run else 'changed'}")
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder-id", default=os.environ.get("GOOGLE_DRIVE_FOLDER_ID"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--all-folders", action="store_true",
                        help="Include older folders for backfills or corrections (default: last seven days)")
    args = parser.parse_args()
    if not args.folder_id:
        parser.error("GOOGLE_DRIVE_FOLDER_ID is required")
    # Import only for live access so routing tests need no Google credentials.
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession

    credentials = service_account.Credentials.from_service_account_info(
        json.loads(os.environ["GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON"]),
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    root = Path(__file__).resolve().parents[1]
    with AuthorizedSession(credentials) as session:
        apply_plan(plan_sync(Drive(session), args.folder_id, root, all_folders=args.all_folders),
                   root, args.dry_run)


if __name__ == "__main__":
    main()
