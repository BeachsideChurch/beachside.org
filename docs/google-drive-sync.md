# Google Drive to GitHub content sync

The **Sync Google Drive content** GitHub Action reads Drive and commits directly
to this repository's default branch. Downloads and Git operations run on a
GitHub-hosted runner; your computer does not need to be running. This is a
one-way sync: Drive content replaces matching destination files. It never
deletes repository files or changes Drive.

## One-time setup

1. In a Google Cloud project, enable the Google Drive API. Create a dedicated
   service account and a JSON key for it. Store the full JSON in the repository's
   **Settings > Secrets and variables > Actions > Secrets**, named
   `GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON`. Do not commit the key or paste it into chat.
2. Share the source Drive folder with the service account's email as **Viewer**.
   Sharing the parent gives access to its weekly subfolders. If Workspace policy
   blocks sharing with service accounts, ask your Workspace administrator to allow
   this dedicated account. No domain-wide delegation is required.
3. Add an Actions **secret** named `GOOGLE_DRIVE_FOLDER_ID` using the ID after
   `/folders/` in the source Drive URL (exclude `?` and any following parameters).
   Keep the actual ID out of committed files. Subfolders are scanned recursively;
   shortcuts are ignored. A manual run's `folder_id` input overrides this secret;
   manual inputs are not secrets, so use the configured secret when privacy matters.
   The sync fails if neither the secret nor a manual folder ID is provided.
   By default, only message folders created within the last seven days are synced.
4. Put the workflow and scripts on the default branch. In **Actions > Sync Google
   Drive content > Run workflow**, leave **dry_run** enabled. Inspect the run log
   for the destination paths. An optional `folder_id` input limits that run to one
   weekly folder, which is useful for initial testing.
5. Run again with **dry_run** unchecked to commit the files. The workflow needs
   permission to write repository contents. Branch protection must permit this
   bot's commits; if the default branch requires pull requests, adapt this workflow
   to a review branch before enabling it. It does not bypass branch protection.
6. For hourly syncing, add an Actions variable `DRIVE_SYNC_ENABLED` with value
   `true`. Otherwise, only manual runs do work. The hourly schedule runs at minute
   17 UTC and can be delayed by GitHub. Remove the variable to stop scheduled syncs.

## Weekly folder format

Folder selection uses Google Drive's actual `createdTime`, not the date in the
folder name, message date, or last edit time. The window is the last 168 hours
at the start of each run, including its lower boundary. Older parent folders
are still traversed to discover recent message folders inside them. The same
filter applies when selecting a single weekly folder with `folder_id`.

Edits sync while the containing message folder is inside that window. **Edits
to older folders will no longer sync automatically.** To import older messages
or apply an older correction, manually run the Action with **all_folders**
enabled, optionally specifying just that week's `folder_id`. For the script,
the equivalent override is `--all-folders`. Scheduled runs always use the
seven-day window. No eligible message folders is a successful run with no changes.

Each message folder must contain exactly one of each:

| Drive file | GitHub destination |
| --- | --- |
| `Watch - 2026-11-01 Just a Chill Guy P2.md` | `content/messages/just-a-chill-guy/Watch - 2026-11-01 Just a Chill Guy P2.md` |
| `Guide - 2026-11-01 Just a Chill Guy P2.md` | `content/discipleship-guide/Guide - 2026-11-01 Just a Chill Guy P2.md` |
| `chillguy.jpg` | `static/images/messages/chillguy.jpg` |

The Markdown files must be uploaded `.md` files with Hugo YAML front matter,
as in the existing repository. Google Docs named with `.md` are rejected.
Transcripts, text files, and other unrelated files are ignored.

The Watch and Guide must have `title`, `date`, and `series`; their dates and
series must match. The Watch must reference the JPG as
`image: /images/messages/chillguy.jpg`. Give the Guide an explicit slug, for
example `slug: chillguy-pt2`, and set the Watch's
`guide_url: /discipleship-guide/chillguy-pt2/`. Other fields and Markdown bodies
are copied byte for byte, including publication status (`draft`). Review Drive
content before syncing published files.

The Watch's `series` selects an existing series directory, ignoring differences
in case and punctuation. For a new series, the sync creates a hyphenated directory
and a basic `_index.md` using the earliest imported Watch's metadata. Multiple
weekly folders with the same `series` go into that same series directory. The
new index's `date` is the earliest imported message date; its `lastmod` is the
latest message date. For existing indexes, only `lastmod` is updated, preserving
other fields, comments, and body content. Dates from existing message files also
count, and syncing an older week never moves `lastmod` backward. This is the
latest message date, not the time the sync ran. Keep Drive filenames stable:
renaming a file creates a new
destination, and the old one must be removed separately. An existing page with
a different filename is not automatically matched by title or slug.

Repeated JPG names are useful for shared series artwork. They must have identical
bytes across all weekly folders included in a run; conflicting files abort the
batch. Use unique image filenames if artwork differs between weeks. Updating an
existing image filename replaces that image everywhere it is referenced.

## Failure behavior and deployment

All selected folders are downloaded and validated before any files are written.
An incomplete weekly upload, conflicting destination, missing front matter,
incorrect link, or failed Drive request fails the whole run without a sync commit.
Finish uploading all three files before running the sync. Folders with neither
a Watch nor a Guide are ignored. Unchanged files produce no commit. Concurrent
sync runs are serialized; if someone pushes after checkout, Git rejects the push
and the next run can retry against the newer branch. No force push is used.

The action uses GitHub's built-in `GITHUB_TOKEN`. Pushes made with that token do
not trigger other GitHub Actions push workflows. If deployment later moves to a
GitHub Actions push workflow, explicitly dispatch that deployment after syncing
or use an appropriately scoped GitHub App token. Verify your existing Netlify
Git integration deploys the first sync commit.

Offline routing tests run in the Action before Drive access. To run them in a
development environment with Python and PyYAML:

```sh
python scripts/test_sync_drive_content.py
```

API references: [Drive file listing](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list),
[Drive downloads](https://developers.google.com/workspace/drive/api/guides/manage-downloads),
[service account authentication](https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.service_account.html),
and [workflow trigger behavior](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
