#!/usr/bin/env node
/**
 * CLOSE-CHECK wrapper for the PIO Panda Forest image-coverage gap (ClickUp 86eyrbw3n).
 *
 * The real check is check_panda_forest_coverage.py — it needs Pillow/numpy to perceptually hash the
 * live Amazon assets against the client's Dropbox set, so it cannot be Node. This wrapper exists so
 * the command is an interpreter on a script file with no shell in it, and so the interpreter path is
 * resolved HERE rather than left to whatever `python` happens to mean in the calling shell (on this
 * box a bare `python`/`py` under Bash is a Windows Store stub that errors).
 *
 * Passes stdout/stderr and the exit code straight through: 0 = ORPHANS-RESOLVED, 1 = STILL-ORPHANED.
 */
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const script = join(here, 'check_panda_forest_coverage.py');

const CANDIDATES = [
  'C:/Users/miraf/AppData/Local/Programs/Python/Python312/python.exe',
  'C:/Users/Erik/AppData/Local/Programs/Python/Python312/python.exe',
];
const py = CANDIDATES.find(existsSync);

if (!py) {
  console.log('PYTHON-MISSING — none of:', CANDIDATES.join(' , '), '— cannot grade');
  process.exit(1);
}
if (!existsSync(script)) {
  console.log('CHECK-MISSING', script, '— cannot grade');
  process.exit(1);
}

const r = spawnSync(py, [script], { stdio: 'inherit' });
process.exit(r.status === null ? 1 : r.status);
