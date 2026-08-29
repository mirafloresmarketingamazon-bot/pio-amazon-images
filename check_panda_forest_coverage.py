"""
CLOSE-CHECK for the PIO Panda Forest image-coverage gap (surfaced 2026-08-26).

Three live slots on `pio-pan-for` -- PT07, PT08 and the colour swatch -- perceptually match NO file
in the client's Dropbox asset set. Every other Panda slot matched at Hamming 0-13 against a
threshold of 26, so these three are almost certainly frames from an older shoot that were never
re-supplied.

This checks the WORLD: it downloads whatever Amazon is serving for those three slots RIGHT NOW and
compares it against the client asset set's perceptual hashes (`client-dhash-2026-08-26.json`,
154 images, committed beside this file so the check survives the temp working dir being deleted).

  exit 0  ORPHANS-RESOLVED  -- all three slots now match a client file (new files were supplied and
                              pushed), or the slots were removed
  exit 1  STILL-ORPHANED    -- at least one slot still matches nothing in the client set

Run:  C:/Users/miraf/AppData/Local/Programs/Python/Python312/python.exe
      C:/Users/miraf/projects/pio-amazon-images/check_panda_forest_coverage.py

NOTE: if the client CONFIRMS the current frames are intended rather than supplying replacements,
this check will keep exiting 1 -- that outcome is a human close with the client's reply pasted in
as the evidence, not an auto-close. See the ticket body.
"""
import json
import os
import subprocess
import sys
import urllib.request

from PIL import Image
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, 'client-dhash-2026-08-26.json')
API = 'C:/Users/miraf/projects/amazon-api-setup'
SKU = 'pio-pan-for'
SLOTS = ('other_product_image_locator_7',
         'other_product_image_locator_8',
         'swatch_product_image_locator')
THRESHOLD = 26


def dh(im, s=16):
    g = im.convert('L').resize((s + 1, s), Image.LANCZOS)
    a = np.asarray(g, dtype=np.int16)
    return np.packbits((a[:, 1:] > a[:, :-1]).flatten()).tobytes()


def ham(a, b):
    return int(np.unpackbits(np.frombuffer(a, dtype=np.uint8) ^ np.frombuffer(b, dtype=np.uint8)).sum())


if not os.path.exists(INDEX):
    print('INDEX-MISSING', INDEX, '- cannot grade')
    sys.exit(1)

src = {k: bytes.fromhex(v) for k, v in json.load(open(INDEX)).items()}

try:
    proc = subprocess.run(['node', 'scripts/pio-read-imgs.mjs', SKU],
                          cwd=API, capture_output=True, text=True, timeout=180)
except Exception as e:
    print('LISTINGS-READ-FAILED', e)
    sys.exit(1)

# FIXED 2026-08-28 (Codex diff review [diffreview:pio-amazon-images@check_panda_forest_coverage.py:59]):
# the old code took only .stdout and never inspected the exit code. If pio-read-imgs.mjs died or read
# a PARTIAL listing after emitting even one unrelated locator line on stdout before failing, every
# target slot missing from that partial output was read as SLOT-REMOVED (line ~83) instead of
# UNKNOWN -- so a failed/partial Amazon read could pass this check and report ORPHANS-RESOLVED.
# Reject the read outright when the subprocess did not exit 0; a failed/partial read must never look
# like resolved orphans.
assert proc.returncode is not None, 'subprocess.run did not populate a return code'
if proc.returncode != 0:
    print('LISTINGS-READ-FAILED - pio-read-imgs.mjs exited', proc.returncode, '(cannot trust stdout as a full read)')
    if proc.stderr:
        print(proc.stderr[-2000:])
    sys.exit(1)

out = proc.stdout

live = {}
for line in out.splitlines():
    parts = line.split()
    if len(parts) == 2 and 'image_locator' in parts[0]:
        live[parts[0]] = parts[1]

if not live:
    print('LISTINGS-READ-EMPTY - cannot grade')
    sys.exit(1)

cache = os.path.join(HERE, '.panda-check-cache')
os.makedirs(cache, exist_ok=True)

orphans = []
for slot in SLOTS:
    aid = live.get(slot)
    if not aid:
        print('%-32s SLOT-REMOVED' % slot)
        continue
    fn = os.path.join(cache, aid)
    try:
        if not os.path.exists(fn):
            req = urllib.request.Request('https://m.media-amazon.com/images/I/' + aid,
                                         headers={'User-Agent': 'Mozilla/5.0'})
            open(fn, 'wb').write(urllib.request.urlopen(req, timeout=60).read())
        t = dh(Image.open(fn))
    except Exception as e:
        print('%-32s FETCH-FAILED %s (%s)' % (slot, aid, e))
        sys.exit(1)
    best_h, best_p = min((ham(t, h), p) for p, h in src.items())
    mark = 'OK' if best_h <= THRESHOLD else 'ORPHAN'
    print('%-32s %-16s ham=%3d  %-6s %s' % (slot, aid, best_h, mark, best_p))
    if best_h > THRESHOLD:
        orphans.append(slot)

if orphans:
    print('STILL-ORPHANED', len(orphans), 'of', len(SLOTS), '-', ', '.join(orphans))
    sys.exit(1)

print('ORPHANS-RESOLVED - every checked slot matches a client file')
sys.exit(0)
