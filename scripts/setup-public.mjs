// SPDX-FileCopyrightText: 2026 Reallexi LLC
// SPDX-License-Identifier: Apache-2.0

import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const publicRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

function run(command, args) {
  return spawnSync(command, args, {
    cwd: publicRoot,
    encoding: 'utf8',
    shell: false,
    windowsHide: true,
  });
}

const nodeMajor = Number.parseInt(process.versions.node.split('.')[0], 10);
if (nodeMajor < 20) {
  console.error('[public] Node.js 20 or newer is required.');
  process.exit(1);
}

const docker = run('docker', ['--version']);
if (docker.status !== 0) {
  console.error('[public] Docker is required for the public launcher.');
  process.exit(1);
}

const compose = run('docker', ['compose', 'version']);
if (compose.status !== 0) {
  console.error('[public] Docker Compose plugin is required.');
  process.exit(1);
}

const envFile = path.join(publicRoot, '.env');
const envExample = path.join(publicRoot, '.env.example');
if (!fs.existsSync(envFile) && fs.existsSync(envExample)) {
  fs.copyFileSync(envExample, envFile);
  console.log('[public] Wrote .env from .env.example.');
}

if (process.env.GITHUB_ACTIONS === 'true') {
  console.log('[public] GitHub Actions detected. Use permissions: packages: read and the automatic GITHUB_TOKEN.');
} else {
  const gh = run('gh', ['auth', 'status', '--hostname', 'github.com']);
  if (gh.status !== 0) {
    console.warn('[public] GitHub CLI is not authenticated. Local private package pulls require GitHub Packages/GHCR access.');
    console.warn('[public] npm login: npm login --scope=@ddkits --auth-type=legacy --registry=https://npm.pkg.github.com');
    console.warn('[public] docker login: docker login ghcr.io');
  }
}

console.log('[public] Setup ok. Login to the private registry/package manager if required, then run npm run project.');
