# Editing website content

Use `/admin/` for forms, or edit the same source files in a text editor. Save
text as UTF-8, indent YAML with two spaces, and use spaces instead of tabs.

## Where content lives

| Content | Source | CMS collection |
| --- | --- | --- |
| Homepage copy, images, cards, service information | `data/home.yaml` | Homepage |
| Homepage title and search description | `content/_index.md` | Homepage |
| Visit, Groups, About, and other regular pages | `content/` | Site Pages |
| Children and student ministry pages | `content/children/`, `content/students/` | Ministry Pages |
| Messages and series | `content/messages/` | Messages by Series; Series (Part 1) |
| Discipleship guides | `content/discipleship-guide/` | Discipleship Guides |
| Live video | `content/watch-live.md` | Watch Live |
| Announcement banner | `data/announcement.yaml` | Announcement Banner |
| Custom standalone pages | `content/landing-pages/` | Landing Pages |

Images live under `static/images/`; their public URLs start with `/images/`.
Edit source files, not generated files in `public/` or `resources/_gen/`.
Keep existing filenames and folder names when changing titles: paths determine
page URLs. The CMS fixes the paths of regular pages and ministry pages.

## Paragraphs and descriptions

The part between `---` lines at the beginning of a Markdown file is YAML
front matter. It holds metadata and, on structured pages, the section content.

Use `|-` for Markdown with paragraphs, lists, or headings. Every line in the
block must be indented farther than its field name. Blank lines separate
paragraphs. The dash means the value has no extra newline at its end.

```yaml
message_recap: |-
  Write the first paragraph here. You can wrap a long sentence onto the
  next source line without creating a new paragraph on the page.

  Start the next paragraph after a blank line.

  **Reflect:** What stood out to you?
```

Use `>-` for a long plain-text description that should remain one paragraph:

```yaml
description: >-
  A short description of the page that is easy to read in a text editor
  and appears as one line of text wherever the site uses it.
```

Aim for source lines around 100–120 characters. Keep links and inline code
intact even when they are longer. Use real line breaks rather than typing
`\n\n` into Markdown. JSON import files are an exception: JSON strings encode
line breaks as `\n`; the importer converts them to readable YAML blocks.

Quote short values containing YAML punctuation, such as `title: "Habits: Prayer"`.
Quote times (`times: "10:45"`) and strings such as `"yes"` or `"no"` that a
YAML parser could mistake for another type. Leave `true` and `false` unquoted
when they are actual switches, such as `draft: true`.

## Lists, emphasis, and links

Use normal Markdown inside text blocks:

```yaml
spiritual_practice: |-
  **Practice for this week**

  1. Find a quiet place.
  2. Read the passage slowly.
  3. Write down one next step.

  Bring a *journal* and your Bible.
  Read [Psalm 23](https://www.bible.com/bible/111/PSA.23.NIV).
```

Avoid unnecessary escapes such as `\&`, `Psalm 1\.`, and `\*journal\*`.
Use an escape only when you want a Markdown punctuation character displayed
literally. `*journal*` produces emphasis; `\*journal\*` displays asterisks.

Use a blank line for a new paragraph. For an intentional line break within
one paragraph, Markdown supports two spaces at the end of the source line;
preserve those spaces when editing. Numbered lists don't need them.

Structured YAML lists are different from Markdown lists. Each devotion is a
YAML item with named fields, and its reflection contains Markdown:

```yaml
daily_devotions:
  - day: Monday
    scripture: Psalm 23:3
    scripture_url: https://www.bible.com/bible/111/PSA.23.3.NIV
    reflection: |-
      Write the day's reflection here.

      **Reflect:** Where do you need guidance today?
  - day: Tuesday
    scripture: John 15:5
    reflection: |-
      Write the next reflection here.
```

Keep all fields of a list item aligned. Optional sections can stay empty:
use `""` for an empty text field and `[]` for an empty list. Keep
`guide_format: structured` on guides so they remain available in the CMS.

## Create and preview content

Create a guide with the prepared fields:

```sh
hugo new content discipleship-guide/my-guide.md
```

For an ordinary Markdown page, use `hugo new content my-page.md`. Both starters
use YAML and begin as drafts. Regular pages with designed sections can be
modeled on `content/visit.md`; adding a new page to the Site Pages CMS collection
also requires an entry in `static/admin/config.yml`.

The single import example is
`imports/discipleship-guide/example-discipleship-guide-import.json`. Copy it to
a new filename before customizing it. See the README's import instructions
for dependency installation and the command. Imported guides start as drafts.

Preview drafts and future-dated messages or guides:

```sh
hugo server --disableFastRender --buildDrafts --buildFuture
```

Open the address printed by Hugo. Check paragraphs, lists, images, links, and
each devotion tab. Preview builds need internet access for the Church Center
events feed. Set `draft: false` when ready; future-dated entries remain excluded
from normal builds until their dates arrive.

For content tooling and schema checks:

```sh
python -m venv /tmp/beachside-guide-tests
/tmp/beachside-guide-tests/bin/pip install -r scripts/requirements.txt
/tmp/beachside-guide-tests/bin/python scripts/test_discipleship_guides.py
/tmp/beachside-guide-tests/bin/python scripts/test_cms_content.py
node scripts/test_cms_yaml.mjs
```

The Node check uses the YAML serializer already bundled with Decap; no npm
packages are needed. CMS saves may reflow source lines, but the check verifies
that paragraph values survive and guide text stays in readable multiline form.
