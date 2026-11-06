"""Smoke checks on tiny sets: generator determinism, every scenario starting cleanly, an A/A diff."""
import filecmp
import os
import shutil

from . import diff, gen, perf, sandbox

N = 12


def same_tree(a, b):
    cmp = filecmp.dircmp(a, b, ignore=['.git'])
    bad = cmp.left_only + cmp.right_only + cmp.diff_files + cmp.funny_files
    return [os.path.join(a, x) for x in bad] + [y for d in cmp.subdirs.values()
                                                 for y in same_tree(d.left, d.right)]


def run(cfg, ref, nvim):
    fails = []
    root = os.path.join(cfg['work'], 'selftest')
    shutil.rmtree(root, ignore_errors=True)
    a, b = gen.generate(f'{root}/a', N, 3), gen.generate(f'{root}/b', N, 3)
    bad = same_tree(a, b)
    print(f"gen determinism (n={N}, twice): {'ok' if not bad else 'FAIL ' + ', '.join(bad[:5])}")
    fails += bad
    rows = [f'{s}{"_" if s[-1].isdigit() else ""}{N}' for s in sandbox.SCENARIOS] + [f'realistic{N}@vimenter',
                                                                                         f'realistic{N}@plugin']
    results = perf.run(cfg, [ref], None, [sandbox.Row(r) for r in rows], 2, [nvim], {'lazy', 'bare', 'native'}, 1,
                       False, os.path.join(root, 'perf.json'))
    for r in results:
        if r['errors'] or any(v.startswith('no report') for v in r['sanity'].values()):
            fails.append(r['row'])
            print(f"FAIL {r['row']}: {r['errors'] or r['sanity']}")
    try:
        diff.lazyvim_dir(cfg)
    except SystemExit:
        print('diff A/A: skipped (no LazyVim data; run zb fetch-lazyvim)')
    else:
        if not diff.run(cfg, ref, [ref], 2, False, nvim):
            fails.append('diff A/A not clean')
    print('SELFTEST ' + ('ok' if not fails else f'FAILED: {fails}'))
    return not fails
