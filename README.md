# Beachside Church Hugo site

This repository contains the source for the Beachside Church website. It is a
static site built with [Hugo](https://gohugo.io/), so the generated site can be
copied to a different web server without running Hugo there.

The site was tested with **Hugo v0.164.0 extended**. Use that version or a newer
compatible extended release when editing or building the site.

## Run the site locally

From the repository root, start Hugo's development server:

```sh
hugo server --disableFastRender
```

Open the local address printed by Hugo, normally
<http://localhost:1313/>. Hugo watches the source files and refreshes the site
as they change. For the browser-based CMS, open
<http://localhost:1313/admin/>. The Decap-powered admin works against the same
Markdown files in `content/` and is configured for the message content model
first. Draft content is hidden by default; include it while reviewing
unpublished work with:

```sh
hugo server --disableFastRender --buildDrafts
```

Stop the server with `Ctrl+C`.

## CMS accounts and password recovery

The editor at `/admin/` uses Decap CMS with Netlify Identity and Git Gateway.
Enable both services on the Netlify project connected to this repository, use
invite-only registration for editors, and ensure Git Gateway targets the `main`
branch. The configured `/.netlify/identity` and `/.netlify/git` endpoints must be
available on the hostname used to open the editor. Copying the static site to
another host does not provide these services automatically.

To reset a password, open `/admin/`, open the Netlify login dialog, and choose
**Forgot password?**. An administrator can also send a reset email from the
project's Netlify Identity user settings. Keep the default email link using
`{{ .ConfirmationURL }}`: landing on the homepage with `#recovery_token=...`
is expected. The homepage loads the Identity widget, which verifies the token
and displays **Update password**. After the password is saved, the editor opens.
Invitation links similarly display a form to choose an initial password.
Links directed to `/admin/` also work; no custom email template is required.

The widget initializes itself on `DOMContentLoaded` and reads the token when
its iframe loads. Do not manually initialize it again, clear the URL fragment,
or force the signup/login dialog while an email callback is pending. Recovery,
invitation, and confirmation tokens have different meanings. Decap handles
admin login in place; the public site's login listener redirects new logins to
`/admin/` without redirecting already signed-in visitors on page load.

After deploying authentication changes, request a fresh reset email and test it
in a private browser window. Confirm that **Update password** appears, save a
new password, then sign out and sign back in with that password. Expired or
previously used links require a fresh email. These checks need the deployed
Identity service; Hugo's development server alone cannot send email or reset
accounts.

Browser regression checks exercise the generated homepage and admin page with
the actual widget and a mocked Identity API. They cover recovery submission,
invitations, expired tokens, recovery-email requests, and normal page loads:

```sh
hugo --gc --minify
python -m venv /tmp/beachside-cms-tests
/tmp/beachside-cms-tests/bin/pip install playwright
/tmp/beachside-cms-tests/bin/playwright install chromium
curl -fsSL https://identity.netlify.com/v1/netlify-identity-widget.js \
  -o /tmp/beachside-identity-widget.js
/tmp/beachside-cms-tests/bin/python scripts/test_cms_identity.py \
  --widget-script /tmp/beachside-identity-widget.js
```

Pass `--browser /path/to/chrome` to use an existing Chrome/Chromium installation.
The tests intercept all browser requests and never send real emails or modify
real accounts. See the [Decap Identity setup guide](https://decapcms.org/docs/choosing-a-backend/)
and [Netlify email documentation](https://docs.netlify.com/manage/security/secure-access-to-sites/identity/identity-generated-emails/).

## Build and deploy

Create an optimized production build from the repository root:

```sh
hugo --gc --minify
```

Hugo writes the complete generated website to `public/`. That directory is
ignored by Git because it is build output. Deploy the **contents** of `public/`
to the destination machine's web root, replacing the previous generated site
as one release. The destination only needs to serve static files; it does not
need Hugo, Git, or this source repository.

Before deploying to another hostname, set `baseURL` in `hugo.toml` to the final
public URL. Never deploy the development server or copy `themes/`, `content/`,
or `assets/` into the web root.

## Where site files live

- `content/` contains editable pages written in Markdown. Front matter at the
  top of each file controls its title, description, images, and other template
  options.
- `data/home.yaml` contains the homepage's repeatable content, such as feature
  cards and location details. Keep its YAML indentation intact and follow the
  field names used by the existing entries.
- `static/images/` contains images copied to the site without modification.
  For example, `static/images/pages/visit.jpg` is referenced in content as
  `/images/pages/visit.jpg`.
- `themes/beachside/` contains the site's Hugo templates, reusable partials,
  source styles, and scripts. Theme CSS and JavaScript live under that theme's
  `assets/` directory.
- `hugo.toml` contains the public URL, site-wide settings, navigation, and the
  announcement banner configuration.

Use lowercase, descriptive, hyphen-separated filenames for new Markdown files
and images. Put general page media in `static/images/pages/`, homepage media in
`static/images/home/`, and message artwork in `static/images/messages/`. Avoid
spaces in filenames. If replacing an image whose dimensions or crop differ,
check both desktop and mobile layouts before publishing.

## Edit pages and navigation

The homepage follows the design in `new-theme/homepage.html`. Edit its copy,
navigation links, ministry cards, and connection links in `data/home.yaml`.
Its layout is in `themes/beachside/layouts/home.html` and its responsive styles
are in `themes/beachside/assets/css/home.css`. The homepage uses locally hosted
Figtree, Big Shoulders Display, and Bitter fonts extracted from the design,
along with its hero and location photos. Interior pages retain their existing
layouts and styles for the next stage of the redesign.

The message feature automatically selects the newest published message with a
video, including series landing pages and individual parts. Its watch button
opens that message. The design's unfinished testimonial placeholders are
replaced with editable Groups and Starting Point cards. The announcement
appears after the homepage footer and can still be dismissed.

The homepage's **Watch live now!** badge links to `/watch-live/` and appears only
on Sundays during the windows in `data/home.yaml` under `hero.live`. The initial
window is **8:45 AM–noon Central**, a provisional choice covering both services;
the legacy site's public HTML omits the scheduled button and does not expose
its exact visibility settings. Confirm these hours with the church when migrating.
Use quoted 24-hour `start` and `end` values; the start is inclusive and the end
is exclusive. Add more windows to show the button separately for each service.
`America/Chicago` handles daylight saving time independently of the visitor's
time zone. The browser checks the schedule on load, every second, and when a
tab resumes, so no scheduled Hugo rebuild is needed. The button stays hidden
until JavaScript determines that a window is active.

Edit an existing Markdown file under `content/` to change a normal page. Keep
the opening and closing front matter delimiters and do not rename fields unless
the matching template is also updated. A page with `draft: true` is available
only when Hugo is run with `--buildDrafts`; change it to `false` when the page
is ready to publish.

The interior pages' primary navigation is configured in `hugo.toml`. Each menu item has a
label, destination, and weight; lower weights appear first. Use root-relative
URLs such as `/visit/` for pages in this site and complete `https://` URLs for
external destinations.

Church Center giving and People form links open in an embedded popup using
Planning Center's script, loaded in the shared head partial. Keep the original
Church Center URL and append `?open-in-church-center-modal=true` (or
`&open-in-church-center-modal=true` if the URL already has a query string).
Use this for `/giving`, fund-specific `/giving/to/...`, and `/people/forms/...`
links, including links entered through the CMS. Existing external-link settings
provide a normal link fallback if the script cannot load.

The popup requires HTTPS on desktop. Planning Center opens a separate browser
window on mobile devices and non-HTTPS local previews. Registration and group
pages do not support embedding and should keep their normal external URLs.
See Planning Center's [form integration instructions](https://help.planningcenter.com/en/139195-integrate-a-form-onto-your-website.html)
and [supported embeds](https://help.planningcenter.com/en/144373-embed-or-link-your-church-center-pages.html).

The optional announcement banner is controlled by the announcement values in
`hugo.toml` under `[params.announcement]`. Set `enabled` to `true` or `false`,
edit its display `text`, and set its destination `url` and link label
`linkText`. Keep an external destination as a complete `https://` URL. If the
banner is not needed, disable it instead of deleting its configuration.

## Add messages and message series

The message templates support both standalone messages and series with any
number of parts. Each part has its own page and `video_url`. The series page is
also Part 1, matching the structure of the original site.

For a new multi-part series, create a branch bundle. Use a lowercase,
hyphen-separated series slug:

```sh
hugo new content --kind message-series messages/built-to-last/_index.md
```

Hugo uses `archetypes/message-series.md` to create the series page. Edit
`content/messages/built-to-last/_index.md` and replace both instances of
`Series Title`. Complete the Part 1 speaker, description, artwork, video, and
optional resource links. Leave `layout: series` and `part_number: 1` in place.

To add Part 2, or any later weekly part, create a page inside that same series
directory:

```sh
hugo new content --kind message-part messages/built-to-last/built-to-last-part-2.md
```

Hugo uses `archetypes/message-part.md`. Edit the new file, make `series` exactly
match the series page, and set the correct `part_number`. Each part requires its
own `video_url`; this is what makes the related links open a different video.
The series navigation is generated automatically from every Markdown file in
the directory, newest first, and excludes the page currently being viewed.
Also update `lastmod` in the series `_index.md` to the new part's date; keep the
series page's original `date` as the Part 1 date.

For a one-week standalone message that will never have additional parts, use:

```sh
hugo new content messages/YYYY-MM-DD-slug.md
```

The standalone command uses `archetypes/messages.md`. Whether editing a series
or standalone message, complete the applicable fields:

```yaml
---
title: "Built to Last"
date: 2026-09-06T09:00:00-05:00
speaker: "Speaker Name"
series: "Series Name"
part_number: 2 # Multi-part series only
description: "A short summary used on message cards and in search previews."
image: "/images/messages/built-to-last.jpg"
video_url: "https://www.youtube.com/watch?v=example"
audio_url: "https://example.org/path/to/audio.mp3"
guide_url: "/discipleship-guide/built-to-last-part-2/"
draft: true
---
```

Then:

1. Add the artwork to `static/images/messages/` and make the `image` value
   match its public `/images/messages/...` path. Leave `image` empty only when
   no artwork is available.
2. Use complete public URLs for `video_url` and `audio_url`. A YouTube watch URL
   or `youtu.be` URL is converted to a privacy-enhanced embed. For a guide in
   this site, use its root-relative URL, such as
   `/discipleship-guide/built-to-last-part-2/`. An externally hosted guide may
   still use a complete `https://` URL. Leave optional URLs empty when they are
   unavailable.
3. Add any longer notes or supporting links below the front matter in Markdown.
4. Preview the message with the draft-enabled development command above.
5. Check the title, date, speaker, series, media links, artwork crop, and message
   page on both narrow and wide screens.
6. Follow every link under **Messages in This Series** and confirm that each
   page loads its own title and video.
7. Change `draft` to `false`, run the production build, and deploy the new
   `public/` output.

Do not edit a generated file in `public/messages/`; Hugo will overwrite it on
the next build. Always edit the corresponding source file in
`content/messages/`.

## Add an independent landing page

**Landing Pages** in `/admin/` manages standalone pages stored in
`content/landing-pages/`. Each page is a Hugo leaf bundle: its own folder with
`index.md`, images, and optional `style.css` and `script.js`. This keeps unrelated
designs together in the repository without forcing them to share the main site's
appearance. See Hugo's [page bundle documentation](https://gohugo.io/content-management/page-bundles/).

In the editor, choose **Landing Pages → New Landing Page**, enter the title,
description and content, and optionally set **Public URL** to an unused path
such as `/vrleaders/`. Without that field, the URL is
`/landing-pages/<page-slug>/`. Keep **Draft** enabled until ready to publish.
Do not reuse an existing page's URL. The example is a draft at
`/landing-page-example/`; it is a starter, not a copy of the existing VR Leaders page.

To create a page with its own stylesheet from the command line:

```sh
hugo new content --kind landing-pages landing-pages/my-campaign
hugo server --disableFastRender --buildDrafts
```

Edit `content/landing-pages/my-campaign/index.md` and `style.css`. Add
`url: /my-campaign/` to the YAML front matter for a shorter URL. Bundle images
can use relative links such as `![Descriptive text](photo.jpg)` even with a
custom URL. The `landing_page: true` marker makes the entry visible in the CMS.

The standalone template loads no main-site navigation, footer, announcement,
styles, or scripts. It uses the bundle's `style.css`, or the minimal
`assets/css/landing-page.css` fallback for pages created in the CMS. If present,
`script.js` is loaded only on that page. Edit those files in the repository;
the CMS edits content and uploads images, not CSS or template code. If a page
needs a Church Center popup or another integration, add that integration to its
custom layout explicitly.

For a completely different structure, create
`layouts/landing-pages/my-design.html` and set `layout: my-design` in the page's
front matter (the **Custom layout** field in the CMS). For example:

```go-html-template
{{ define "main" }}
<section class="campaign">
  <h1>{{ .Title }}</h1>
  {{ .Content }}
</section>
{{ end }}
```

The shared standalone `baseof.html` provides metadata, a viewport tag, a skip
link, and page-specific assets. A custom layout can also define a `head` block.
Keep keyboard focus styling and the skip link usable in custom stylesheets.

The section's `_index.md` applies Hugo
[build options](https://gohugo.io/content-management/build-options/) to exclude
landing pages from page collections, including site search, feeds, and the
sitemap, while still publishing each non-draft page at its URL. There is no
public landing-page directory. No navigation links are added automatically.
**Hide from search engines** adds a `noindex` request by default; turning it off
allows indexing but does not add the page to listings or the sitemap.
Unlisted pages are public, not password-protected. Drafts are omitted from normal
production builds.

## Add a discipleship guide

The guide archive is generated at `/discipleship-guides/`. Individual guides
live at `/discipleship-guide/<guide-slug>/`; they are intentionally not added to
the homepage or primary navigation. Create a guide with:

```sh
hugo new content discipleship-guide/built-to-last-part-2.md
```

In Decap at `/admin/`, select **Discipleship Guides**, then open an existing
entry or choose **New Discipleship Guide**. All existing guides use the same
structured fields as new guides. Complete the title, date, speaker, series,
description, and optional video URL. **Show series in title panel** controls
whether the series appears above the title.

Guide sections start collapsed in the CMS. Click a section heading to expand
it; collapsed lists hide their entries so Daily Devotions stays easy to reach.

Edit Message Recap, Main Idea, Spiritual Practice, and Additional content with
the Markdown editor. Discussion questions, daily devotions, prayer prompts,
next steps, and resources have repeatable fields: add, remove, or reorder items
using the list controls. Each devotion has a day label, Scripture reference,
Scripture URL, and reflection. New guides start with Monday through Friday;
you can use other labels or add more days. Empty optional sections are hidden.

Leave **Draft** enabled while preparing a guide; disable it when ready for the
public site. Set the corresponding message's `guide_url` to the guide's
root-relative path, such as `/discipleship-guide/built-to-last-part-2/`, and
preview the guide and each devotion tab before publishing.

The CLI command above uses `archetypes/discipleship-guide.md` to create the same
structured YAML front matter. `guide_format: structured` identifies guide
entries for Decap and the Hugo renderer; keep it in place. The archive's
`_index.md` is excluded from this collection. Section content supports Markdown
and existing HTML; layout markup is generated by the theme. The optional body
appears after Resources as Additional content.

Do not edit generated files under `public/discipleship-guide/` or
`public/discipleship-guides/`; they are overwritten by Hugo.

## Import a discipleship guide from JSON

A structured JSON import flow is available for creating new discipleship guide
files from a consistent payload rather than hand-writing the full guide HTML.
Keep your source JSON files in `imports/discipleship-guide/` and name them with a
clear slug such as `example-discipleship-guide-import.json`.

From the repository root, run the importer directly with:

```sh
python scripts/import_discipleship_guide.py \
  --input imports/discipleship-guide/example-discipleship-guide-import.json \
  --output-dir content/discipleship-guide \
  --force
```

The script reads the input JSON and writes a Hugo Markdown guide with the same
structured front matter used by Decap to the
`content/discipleship-guide/` directory. The template converts YouTube URLs into
embeds. Imported Markdown and HTML are both supported, and imported guides
start as drafts. The generated file uses the guide title
and, when present, the series name to create a slug, for example:

```text
series-name-optional--message-title.md
```

The importer is intentionally safe by default: if the generated file already
exists, it exits without overwriting it. Add `--force` only when you mean to
replace the existing guide file with a fresh import.

To use the GitHub Actions workflow instead, open the repo in GitHub and run the
`Import discipleship guide` action from the Actions tab. The workflow is set to
default to `imports/discipleship-guide/example-discipleship-guide-import.json`,
but you can change the `json_path` input to point at another import file in the
repository before running it.

The workflow performs these steps automatically:

1. Checks out the repository.
2. Sets up Python 3.12.
3. Runs the importer script with your selected JSON file.
4. Commits any newly generated guide file back to the repository.
5. Pushes the commit to the branch.

This is a good fit for repeatable guide creation when a message series will have
many guides with the same structure.

To check the guide schema, JSON import, section rendering, and devotion tab
structure after changes:

```sh
python -m venv /tmp/beachside-guide-tests
/tmp/beachside-guide-tests/bin/pip install pyyaml beautifulsoup4
/tmp/beachside-guide-tests/bin/python scripts/test_discipleship_guides.py
```

## Pre-deployment check

Before copying a release, run the production build and review its output for
warnings. Check the homepage, navigation at mobile and desktop widths, internal
links, external Church Center actions, and the newest message. Commit source
changes only; generated files in `public/` and `resources/_gen/` should remain
untracked.
