// SPDX-FileCopyrightText: 2026 Reallexi LLC
// SPDX-License-Identifier: Apache-2.0

import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const publicRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: publicRoot,
    encoding: 'utf8',
    shell: false,
    stdio: options.stdio || 'inherit',
    windowsHide: true,
  });
  if (result.status !== 0) process.exit(result.status || 1);
}

run(process.execPath, [path.join(publicRoot, 'scripts/validate-public.mjs')]);
run('docker', ['compose', 'up', '-d'], { stdio: 'inherit' });
console.log('[public] UI:  http://localhost:55173');
console.log('[public] API: http://localhost:58080');
