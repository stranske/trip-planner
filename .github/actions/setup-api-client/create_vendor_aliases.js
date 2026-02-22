#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const installDirArg = process.argv[2];

if (!installDirArg) {
  console.error('Usage: create_vendor_aliases.js <install_dir>');
  process.exit(1);
}

const installDir = path.resolve(installDirArg);
const pkgPath = path.join(installDir, 'package.json');

if (!fs.existsSync(pkgPath)) {
  process.exit(0);
}

const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
const sections = [pkg.dependencies || {}, pkg.devDependencies || {}];
const seen = new Set();

for (const section of sections) {
  for (const spec of Object.values(section)) {
    if (typeof spec === 'string' && spec.startsWith('file:node_modules/')) {
      const trimmed = spec.slice('file:node_modules/'.length).replace(/\/+$/, '');
      if (trimmed) {
        seen.add(trimmed);
      }
    }
  }
}

const sanitize = (value) => {
  if (typeof value !== 'string') {
    throw new Error('Vendored alias must be a string');
  }

  const normalized = value.trim();
  if (!normalized) {
    throw new Error('Vendored alias cannot be empty');
  }
  if (normalized.startsWith('/') || normalized.startsWith('./') || normalized.startsWith('../')) {
    throw new Error(`Vendored alias must be relative: "${normalized}"`);
  }
  if (normalized.includes('\\')) {
    throw new Error(`Vendored alias must not contain backslashes: "${normalized}"`);
  }

  const segments = normalized.split('/');
  if (segments[0].startsWith('@')) {
    if (!/^@[A-Za-z0-9._-]+$/.test(segments[0])) {
      throw new Error(`Invalid scope in vendored alias: "${normalized}"`);
    }
    if (segments.length < 2) {
      throw new Error(`Scoped vendored alias must include a package name: "${normalized}"`);
    }
  }

  const segmentPattern = /^[A-Za-z0-9._-]+$/;
  for (let i = 0; i < segments.length; i += 1) {
    const segment = segments[i];
    if (!segment || segment === '.' || segment === '..') {
      throw new Error(`Invalid path segment "${segment}" in "${normalized}"`);
    }
    if (segment.startsWith('@')) {
      if (i !== 0 || !/^@[A-Za-z0-9._-]+$/.test(segment)) {
        throw new Error(`Invalid scope segment "${segment}" in "${normalized}"`);
      }
      continue;
    }
    if (!segmentPattern.test(segment)) {
      throw new Error(`Vendored alias segment "${segment}" contains invalid characters in "${normalized}"`);
    }
  }

  return segments.join('/');
};

const created = [];
for (const alias of seen) {
  const sanitized = sanitize(alias);
  const source = path.join(installDir, 'node_modules', sanitized);
  if (!fs.existsSync(source)) {
    console.warn(`::warning::Vendored dependency not found: ${sanitized}`);
    continue;
  }
  const destination = path.join(installDir, sanitized);
  const normalizedDestination = path.normalize(destination);
  if (!normalizedDestination.startsWith(installDir + path.sep) && normalizedDestination !== installDir) {
    throw new Error(`Resolved vendored alias outside install dir: "${sanitized}"`);
  }
  fs.rmSync(destination, { recursive: true, force: true });
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.cpSync(source, destination, { recursive: true });
  created.push(sanitized);
}

process.stdout.write(created.join('\n'));
