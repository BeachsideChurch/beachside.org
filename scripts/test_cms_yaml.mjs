// Run with Node: exercise the exact YAML serializer shipped in Decap's bundle.
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, basename } from 'node:path';
import { pathToFileURL } from 'node:url';

const root = new URL('../', import.meta.url);
const map = JSON.parse(await readFile(new URL('static/admin/decap-cms.js.map', root), 'utf8'));
const temp = await mkdtemp(join(tmpdir(), 'beachside-cms-yaml-'));
try {
  await writeFile(join(temp, 'package.json'), '{"type":"module"}');
  for (let i = 0; i < map.sources.length; i++) {
    const source = map.sources[i];
    if (source.includes('/yaml/browser/dist/')) {
      await writeFile(join(temp, basename(source)), map.sourcesContent[i]);
    }
    if (source.endsWith('/formats/helpers.js')) {
      await writeFile(join(temp, 'helpers.js'), map.sourcesContent[i]);
    }
    if (source.endsWith('/formats/yaml.js')) {
      await writeFile(join(temp, 'formatter.js'), map.sourcesContent[i]
        .replace("import yaml from 'yaml';", "import { YAML as yaml } from './index.js';")
        .replace("from './helpers'", "from './helpers.js'"));
    }
  }
  const { default: formatter } = await import(pathToFileURL(join(temp, 'formatter.js')));
  const prose = '**Heading**  \nA hard break.\n\nA new paragraph.';
  const sample = { spiritual_practice: prose, daily_devotions: [{ day: 'Monday', reflection: prose }] };
  const output = formatter.toFile(sample);
  assert.deepEqual(formatter.fromFile(output), sample);
  assert.ok(output.includes('spiritual_practice: |-'));
  assert.ok(!output.includes('\\n'));
  const guides = new URL('content/discipleship-guide/', root);
  for (const name of await readdir(guides)) {
    if (!name.endsWith('.md')) continue;
    const source = (await readFile(new URL(name, guides), 'utf8')).split('---')[1];
    const data = formatter.fromFile(source);
    const saved = formatter.toFile(data);
    assert.deepEqual(formatter.fromFile(saved), data, name);
    assert.ok(!saved.includes('\\n'), name);
  }
  const config = formatter.fromFile(await readFile(new URL('static/admin/config.yml', root), 'utf8'));
  for (const collection of config.collections.filter(c => ['homepage', 'site_pages', 'ministry_pages'].includes(c.name))) {
    for (const entry of collection.files) {
      const source = await readFile(new URL(entry.file, root), 'utf8');
      const data = formatter.fromFile(entry.file.endsWith('.md') ? source.split('---')[1] : source);
      assert.deepEqual(formatter.fromFile(formatter.toFile(data)), data, entry.file);
    }
  }
  console.log('Bundled CMS YAML preserves guides, homepage data, and page content, including shared field anchors.');
} finally {
  await rm(temp, { recursive: true, force: true });
}
