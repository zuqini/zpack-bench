"""Smoke checks on tiny sets: generator determinism, every scenario starting cleanly, an A/A diff."""
import filecmp
import glob
import hashlib
import json
import os
import shutil

from . import diff, gen, perf, sandbox

N = 12


def same_tree(a, b):
    cmp = filecmp.dircmp(a, b, ignore=['.git'])
    bad = cmp.left_only + cmp.right_only + cmp.diff_files + cmp.funny_files
    return [os.path.join(a, x) for x in bad] + [y for d in cmp.subdirs.values()
                                                 for y in same_tree(d.left, d.right)]


def config_sha1(d):
    m = hashlib.sha1()
    for f in sorted(glob.glob(f'{d}/plugins/*.lua')):
        m.update(os.path.basename(f).encode())
        m.update(open(f, 'rb').read())
    return m.hexdigest()


def pinned(cfg):
    """The 150-plugin seed-1 configs must not drift: realistic, eager, inits and inits10 were byte-identical to the
    PR #54 bench's output when pinned (DESIGN.md); trig/trig10 differ from it only in the ft functions' targets."""
    pins = json.load(open(os.path.join(os.path.dirname(__file__), 'pinned.json')))
    sd = gen.set_dir(cfg, pins['n'], pins['seed'])
    return [s for s, h in pins['config_sha1'].items() if config_sha1(f'{sd}/configs/{s}') != h]


def run(cfg, ref, nvim):
    fails = []
    drift = pinned(cfg)
    print(f"pinned 150-plugin configs: {'ok' if not drift else 'DRIFTED ' + ', '.join(drift)}")
    fails += drift
    root = os.path.join(cfg['work'], 'selftest')
    shutil.rmtree(root, ignore_errors=True)
    a, b = gen.generate(f'{root}/a', N, 3), gen.generate(f'{root}/b', N, 3)
    bad = same_tree(a, b)
    print(f"gen determinism (n={N}, twice): {'ok' if not bad else 'FAIL ' + ', '.join(bad[:5])}")
    fails += bad
    rows = [f'{s}{"_" if s[-1].isdigit() else ""}{N}' for s in sandbox.SCENARIOS] + [f'realistic{N}@vimenter',
                                                                                         f'realistic{N}@plugin']
    results = perf.run_rows(cfg, [ref], None, [sandbox.Row(r) for r in rows], 2, [nvim], {'lazy', 'bare', 'native'},
                            1, os.path.join(root, 'perf.json'))
    for r in results:
        f = [x for x in perf.flags(r, cfg['max_load']) if x in ('ERRORS', 'SANITY')]
        if f:
            fails.append(r['row'])
            print(f"FAIL {r['row']}: {f} {r['errors'] or r['sanity']}")
    try:
        diff.lazyvim_dir(cfg)
    except SystemExit:
        print('diff A/A: skipped (no LazyVim data; run zb fetch-lazyvim)')
    else:
        if not diff.run(cfg, ref, [ref], 2, False, nvim):
            fails.append('diff A/A not clean')
    print('SELFTEST ' + ('ok' if not fails else f'FAILED: {fails}'))
    return not fails
