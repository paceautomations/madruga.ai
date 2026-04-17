import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import remarkResolveLinks, { resolveLink } from '../src/lib/remarkResolveLinks.mjs';

function withFixture(fn) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'remark-resolve-'));
  const platformsDir = path.join(root, 'platforms');
  const p = path.join(platformsDir, 'prosauai');

  fs.mkdirSync(path.join(p, 'business'), { recursive: true });
  fs.mkdirSync(path.join(p, 'engineering'), { recursive: true });
  fs.mkdirSync(path.join(p, 'decisions'), { recursive: true });
  fs.mkdirSync(path.join(p, 'epics', '006-production-readiness'), { recursive: true });

  for (const f of [
    'business/process.md', 'business/vision.md',
    'engineering/blueprint.md', 'engineering/domain-model.md', 'engineering/containers.md',
    'decisions/ADR-011-pool.md', 'decisions/ADR-024-schema.md',
    'epics/006-production-readiness/pitch.md',
  ]) {
    fs.writeFileSync(path.join(p, f), '# ' + f);
  }

  try {
    return fn({ root, platformsDir, p });
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}

test('cross-section: rewrites to absolute URL', () => {
  withFixture(({ platformsDir, p }) => {
    const out = resolveLink('../engineering/domain-model/', path.join(p, 'business'), platformsDir);
    assert.equal(out, '/prosauai/engineering/domain-model/');
  });
});

test('same-section URL-style path: target not on disk → null (plugin lets browser resolve)', () => {
  withFixture(({ platformsDir, p }) => {
    const out = resolveLink('../containers/', path.join(p, 'engineering'), platformsDir);
    assert.equal(out, null);
  });
});

test('epic nested: ../../engineering/blueprint/ resolves', () => {
  withFixture(({ platformsDir, p }) => {
    const out = resolveLink('../../engineering/blueprint/', path.join(p, 'epics', '006-production-readiness'), platformsDir);
    assert.equal(out, '/prosauai/engineering/blueprint/');
  });
});

test('anchor preservation', () => {
  withFixture(({ platformsDir, p }) => {
    const out = resolveLink('../engineering/blueprint/#containers', path.join(p, 'business'), platformsDir);
    assert.equal(out, '/prosauai/engineering/blueprint/#containers');
  });
});

test('query preservation', () => {
  withFixture(({ platformsDir, p }) => {
    const out = resolveLink('../engineering/domain-model/?q=1', path.join(p, 'business'), platformsDir);
    assert.equal(out, '/prosauai/engineering/domain-model/?q=1');
  });
});

test('.md extension: strips and lowercases', () => {
  withFixture(({ platformsDir, p }) => {
    const out = resolveLink('../decisions/ADR-024-schema.md', path.join(p, 'business'), platformsDir);
    assert.equal(out, '/prosauai/decisions/adr-024-schema/');
  });
});

test('external http: skip', () => {
  withFixture(({ platformsDir, p }) => {
    const srcDir = path.join(p, 'business');
    assert.equal(resolveLink('https://example.com', srcDir, platformsDir), null);
    assert.equal(resolveLink('http://x', srcDir, platformsDir), null);
    assert.equal(resolveLink('mailto:a@b.com', srcDir, platformsDir), null);
  });
});

test('absolute / path: skip', () => {
  withFixture(({ platformsDir, p }) => {
    assert.equal(resolveLink('/prosauai/already-absolute/', path.join(p, 'business'), platformsDir), null);
  });
});

test('pure fragment: skip', () => {
  withFixture(({ platformsDir, p }) => {
    assert.equal(resolveLink('#section', path.join(p, 'business'), platformsDir), null);
  });
});

test('outside platforms/: skip', () => {
  withFixture(({ platformsDir, p }) => {
    assert.equal(resolveLink('../../../outside/thing/', path.join(p, 'business'), platformsDir), null);
  });
});

test('target does not exist: skip (browser handles URL-style)', () => {
  withFixture(({ platformsDir, p }) => {
    assert.equal(resolveLink('../engineering/nonexistent/', path.join(p, 'business'), platformsDir), null);
  });
});

test('ADR with complex name: lowercases to match Starlight slug', () => {
  withFixture(({ platformsDir, p }) => {
    const out = resolveLink('../decisions/ADR-011-pool/', path.join(p, 'engineering'), platformsDir);
    assert.equal(out, '/prosauai/decisions/adr-011-pool/');
  });
});

test('plugin: rewrites link nodes in MDAST tree', () => {
  withFixture(({ platformsDir, p }) => {
    const sourceFile = path.join(p, 'business', 'process.md');
    const tree = {
      type: 'root',
      children: [
        {
          type: 'paragraph',
          children: [
            { type: 'link', url: '../engineering/domain-model/', children: [{ type: 'text', value: 'DM' }] },
            { type: 'link', url: '../engineering/blueprint/#containers', children: [{ type: 'text', value: 'BP' }] },
            { type: 'link', url: 'https://example.com', children: [{ type: 'text', value: 'ext' }] },
          ],
        },
        { type: 'definition', identifier: 'ref1', url: '../decisions/ADR-011-pool.md' },
      ],
    };

    remarkResolveLinks({ platformsDir })(tree, { history: [sourceFile] });

    assert.equal(tree.children[0].children[0].url, '/prosauai/engineering/domain-model/');
    assert.equal(tree.children[0].children[1].url, '/prosauai/engineering/blueprint/#containers');
    assert.equal(tree.children[0].children[2].url, 'https://example.com');
    assert.equal(tree.children[1].url, '/prosauai/decisions/adr-011-pool/');
  });
});

test('plugin: source outside platforms/ → no-op', () => {
  withFixture(({ root, platformsDir }) => {
    const sourceFile = path.join(root, 'outside.md');
    fs.writeFileSync(sourceFile, '# outside');
    const tree = {
      type: 'root',
      children: [{ type: 'link', url: '../platforms/prosauai/engineering/blueprint/', children: [] }],
    };

    remarkResolveLinks({ platformsDir })(tree, { history: [sourceFile] });

    assert.equal(tree.children[0].url, '../platforms/prosauai/engineering/blueprint/');
  });
});

test('plugin: requires platformsDir option', () => {
  assert.throws(() => remarkResolveLinks({}), /platformsDir/);
});
