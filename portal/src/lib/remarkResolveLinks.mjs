import fs from 'node:fs';
import path from 'node:path';

const EXTERNAL_OR_ABSOLUTE = /^(https?:|mailto:|tel:|data:|\/|#)/;

function splitSuffix(url) {
  const hashIdx = url.indexOf('#');
  const queryIdx = url.indexOf('?');
  let cut = -1;
  if (hashIdx >= 0 && queryIdx >= 0) cut = Math.min(hashIdx, queryIdx);
  else if (hashIdx >= 0) cut = hashIdx;
  else if (queryIdx >= 0) cut = queryIdx;
  if (cut < 0) return [url, ''];
  return [url.slice(0, cut), url.slice(cut)];
}

function isFile(p) {
  try { return fs.statSync(p).isFile(); } catch { return false; }
}
function isDirectory(p) {
  try { return fs.statSync(p).isDirectory(); } catch { return false; }
}

const existsCache = new Map();
function targetExists(resolved) {
  const cached = existsCache.get(resolved);
  if (cached !== undefined) return cached;
  const exists = isFile(resolved + '.md')
    || isFile(path.join(resolved, 'index.md'))
    || isDirectory(resolved);
  existsCache.set(resolved, exists);
  return exists;
}

export function resolveLink(url, sourceDir, platformsDir) {
  if (!url || EXTERNAL_OR_ABSOLUTE.test(url)) return null;

  const [pathPart, suffix] = splitSuffix(url);
  if (!pathPart) return null;

  const normalized = pathPart.replace(/\/$/, '').replace(/\.md$/, '');
  if (!normalized) return null;

  const resolved = path.resolve(sourceDir, normalized);
  const platformsRoot = platformsDir.replace(/\/$/, '');
  if (!(resolved === platformsRoot || resolved.startsWith(platformsRoot + path.sep))) {
    return null;
  }

  if (!targetExists(resolved)) return null;

  const rel = path.relative(platformsRoot, resolved);
  if (!rel || rel.startsWith('..') || path.isAbsolute(rel)) return null;

  const urlPath = '/' + rel.split(path.sep).join('/').toLowerCase() + '/';
  return urlPath + suffix;
}

function visitLinkNodes(node, visitor) {
  if (!node || typeof node !== 'object') return;
  if (node.type === 'link' || node.type === 'definition') visitor(node);
  if (Array.isArray(node.children)) {
    for (const child of node.children) visitLinkNodes(child, visitor);
  }
}

export default function remarkResolveLinks(options = {}) {
  const platformsDir = options.platformsDir;
  if (!platformsDir) {
    throw new Error('remarkResolveLinks requires options.platformsDir');
  }

  return function transformer(tree, file) {
    const sourcePath = file?.history?.[0] ?? file?.path;
    if (!sourcePath) return;

    let realSource;
    try {
      realSource = fs.realpathSync(sourcePath);
    } catch {
      return;
    }

    const platformsRoot = platformsDir.replace(/\/$/, '');
    if (!realSource.startsWith(platformsRoot + path.sep)) return;

    const sourceDir = path.dirname(realSource);

    visitLinkNodes(tree, (node) => {
      const rewritten = resolveLink(node.url, sourceDir, platformsRoot);
      if (rewritten !== null) {
        node.url = rewritten;
      }
    });
  };
}
