// SPDX-FileCopyrightText: 2026 Reallexi LLC
// SPDX-License-Identifier: Apache-2.0

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const publicRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const inRoot = (file) => path.join(publicRoot, file);

const required = [
  'README.md',
  'AGENTS.md',
  'LICENSE',
  'NOTICE',
  'COPYRIGHT.md',
  'CONTRIBUTING.md',
  'CODE_OF_CONDUCT.md',
  'SECURITY.md',
  'SUPPORT.md',
  'GOVERNANCE.md',
  'docker-compose.yml',
  'package.json',
  'reallexi.public.json',
  'core/reallexi-core-access.json.gz',
  'core/reallexi-core-access.sha256',
  'docs/README.md',
  'docs/CORE_DISTRIBUTION_GITHUB.md',
  'docs/EXTENSIONS.md',
  'docs/FEATURE_ACCESS_GUIDE.md',
  'docs/PLUGIN_HOOKS.md',
  'docs/PERSONAL_COMMERCIAL_POLICY.md',
  'docs/SPONSORSHIP.md',
  'docs/PUBLIC_REPOSITORY_GUIDE.md',
  'docs/RELEASE_PROFILES.md',
  'docs/SUPPORT_SLM_STACK.md',
  'docs/MODEL_ARTIFACTS.md',
  'docs/HUGGINGFACE_WORKSPACE.md',
  'docs/PHASED_TRAINING.md',
  'docs/GPU_ACCELERATION.md',
  'docs/TRAINING_DATA_SOURCES.md',
  'scripts/setup-public.mjs',
  'scripts/validate-public.mjs',
  'scripts/project-public.mjs',
];

const allowedFiles = new Set([
  ...required,
  '.env.example',
  '.gitignore',
  '.npmrc.example',
  'agent.md',
  'core/README.md',
  'core/reallexi-core-access.json',
  'docs/PUBLIC_PRIVATE_ARCHITECTURE.md',
  'package-managers/core-package.json',
  'package-managers/npmrc.github-packages.example',
  '.github/FUNDING.yml',
  '.github/dependabot.yml',
  '.github/pull_request_template.md',
  '.github/ISSUE_TEMPLATE/bug_report.yml',
  '.github/ISSUE_TEMPLATE/feature_request.yml',
]);

const missing = required.filter((file) => !fs.existsSync(inRoot(file)));
if (missing.length > 0) {
  console.error('[public] Missing required files: ' + missing.join(', '));
  process.exit(1);
}

const fundingConfig = fs.readFileSync(inRoot('.github/FUNDING.yml'), 'utf8');
for (const requiredFunding of [
  'github: ddkits',
  'buy_me_a_coffee: ddkits',
  'https://reallexi.io/sponsor',
]) {
  if (!fundingConfig.includes(requiredFunding)) {
    console.error('[public] Missing canonical funding channel: ' + requiredFunding);
    process.exit(1);
  }
}

function collectFiles(directory) {
  const files = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (['.git', '.env', 'data', 'node_modules'].includes(entry.name)) continue;
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...collectFiles(target));
    if (entry.isFile()) files.push(target);
  }
  return files;
}

const allFiles = collectFiles(publicRoot);
const relative = (file) => path.relative(publicRoot, file).replaceAll(path.sep, '/');
const unexpectedFiles = allFiles.map(relative).filter((file) => !allowedFiles.has(file));
if (unexpectedFiles.length > 0) {
  console.error('[public] Files outside the public allowlist: ' + unexpectedFiles.join(', '));
  process.exit(1);
}

const forbiddenSourceExtensions = new Set(['.py', '.pyc', '.jsx', '.tsx', '.map']);
const sourceLeaks = allFiles
  .map(relative)
  .filter((file) => forbiddenSourceExtensions.has(path.extname(file).toLowerCase()));
if (sourceLeaks.length > 0) {
  console.error('[public] Source or source-map files are not allowed: ' + sourceLeaks.join(', '));
  process.exit(1);
}

const publicTextFiles = allFiles.filter((file) => {
  const fileName = relative(file);
  const extension = path.extname(fileName).toLowerCase();
  return ['.md', '.html', '.css', '.yml', '.yaml'].includes(extension);
});

const packageMetadata = JSON.parse(fs.readFileSync(inRoot('package.json'), 'utf8'));
const publicScripts = new Set(Object.keys(packageMetadata.scripts || {}));
const allowedGithubPrefixes = [
  'https://github.com/ddkits/reallexi-ai-model-builder',
  'https://github.com/sponsors/ddkits',
];

for (const file of publicTextFiles) {
  const content = fs.readFileSync(file, 'utf8');

  if (/[A-Za-z]:\\Users\\|\/home\/[^/\s]+\/|\/Users\/[^/\s]+\//.test(content)) {
    console.error('[public] Absolute local path in ' + relative(file));
    process.exit(1);
  }

  for (const match of content.matchAll(/npm(?:\.cmd)? run ([A-Za-z0-9:_-]+)/g)) {
    if (!publicScripts.has(match[1])) {
      console.error('[public] Undeclared npm command in ' + relative(file) + ': ' + match[1]);
      process.exit(1);
    }
  }

  for (const match of content.matchAll(/https:\/\/github\.com\/[^\s)>'"]+/g)) {
    if (!allowedGithubPrefixes.some((prefix) => match[0].startsWith(prefix))) {
      console.error('[public] Unapproved GitHub repository link in ' + relative(file));
      process.exit(1);
    }
  }

  if (/(?:X-[A-Za-z0-9-]*Token|\/(?:api|admin)\/[A-Za-z0-9_/{.-]+)/i.test(content)) {
    console.error('[public] Internal endpoint or token-header detail in ' + relative(file));
    process.exit(1);
  }

  if (path.extname(file).toLowerCase() === '.md') {
    for (const match of content.matchAll(/\[[^\]]+\]\(([^)]+)\)/g)) {
      const target = match[1].trim().split(/\s+/)[0].replace(/^<|>$/g, '');
      if (/^(?:https?:|mailto:|#)/i.test(target)) continue;
      const localTarget = decodeURIComponent(target.split('#')[0]);
      if (!fs.existsSync(path.resolve(path.dirname(file), localTarget))) {
        console.error('[public] Broken local documentation link in ' + relative(file) + ': ' + target);
        process.exit(1);
      }
    }
  }
}

function assertOnlyKeys(value, allowed, label) {
  const unexpected = Object.keys(value || {}).filter((key) => !allowed.includes(key));
  if (unexpected.length > 0) {
    console.error('[public] Unexpected metadata in ' + label + ': ' + unexpected.join(', '));
    process.exit(1);
  }
}

assertOnlyKeys(packageMetadata.reallexi, [
  'generatedAt',
  'publicRepository',
  'privateCorePackage',
  'backendImage',
  'frontendImage',
], 'package.json reallexi block');

const publicManifest = JSON.parse(fs.readFileSync(inRoot('reallexi.public.json'), 'utf8'));
assertOnlyKeys(publicManifest.repositories, ['public'], 'public repository list');
if (publicManifest.publicBoundary?.githubPagesHostedHere !== false) {
  console.error('[public] GitHub Pages must be disabled for this repository.');
  process.exit(1);
}

const accessMetadata = JSON.parse(fs.readFileSync(inRoot('core/reallexi-core-access.json'), 'utf8'));
assertOnlyKeys(accessMetadata, [
  'generatedAt',
  'owner',
  'version',
  'publicRepository',
  'publicPackage',
  'privateCorePackage',
  'backendImage',
  'frontendImage',
  'packageManagers',
  'integrity',
], 'core access metadata');
assertOnlyKeys(accessMetadata.packageManagers, ['npm', 'githubPackages', 'ociImages'], 'package managers');

const compose = fs.readFileSync(inRoot('docker-compose.yml'), 'utf8');
for (const match of compose.matchAll(/(?<!\d)(\d{4,5})(?!\d)/g)) {
  const port = Number.parseInt(match[1], 10);
  if (port < 54376 || port > 64322) {
    console.error('[public] Port out of allowed range: ' + port);
    process.exit(1);
  }
}

console.log('[public] Validation complete.');
