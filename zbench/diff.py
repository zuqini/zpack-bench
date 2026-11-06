"""Functional differential: LazyVim (all extras + seeded subsets) and the live config through zpack refs.

Reports lazy= flips first, then structure (P/E/W lines), opts, errors; optionally the lazy.nvim oracle.
"""
import collections
import glob
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

from . import config, sandbox, trees

LIVE_SPEC = "return { { import = 'plugins' } }\n"


def lazyvim_dir(cfg):
    dirs = sorted(glob.glob(os.path.join(cfg['work'], 'data', 'lazyvim', '*', '')))
    if not dirs:
        raise SystemExit('no LazyVim data: run `zb fetch-lazyvim` first')
    return dirs[0].rstrip('/')


def fetch_lazyvim(cfg, sha=None):
    """Download LazyVim's source as data; it is parsed with Tree-sitter, never executed."""
    if not sha:
        sha = subprocess.run(['gh', 'api', 'repos/LazyVim/LazyVim/commits/main', '-q', '.sha'], check=True,
                             capture_output=True, text=True).stdout.strip()
    dest = os.path.join(cfg['work'], 'data', 'lazyvim')
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    tar = subprocess.Popen(['gh', 'api', f'repos/LazyVim/LazyVim/tarball/{sha}'], stdout=subprocess.PIPE)
    subprocess.run(['tar', '-xz', '-C', dest], stdin=tar.stdout, check=True)
    if tar.wait():
        raise SystemExit('LazyVim download failed')
    open(os.path.join(dest, 'SHA'), 'w').write(sha + '\n')
    print(f'LazyVim {sha} -> {lazyvim_dir(cfg)}')


def live_sandbox(cfg):
    """XDG-isolated copy of the live config: the import may call the real vim.pack.add."""
    root = os.path.join(cfg['work'], 'diff', 'live')
    shutil.rmtree(root, ignore_errors=True)
    sandbox.clone(cfg['user_config'], f'{root}/config/nvim')
    with open(f'{root}/live.lua', 'w') as f:
        f.write(LIVE_SPEC)
    return root


def run_zpack(cfg, nvim, tree, inp, mode, seed, out, env=None):
    with open(out, 'w') as f:
        p = subprocess.run([nvim, '-u', 'NONE', '-l', os.path.join(config.LUA, 'run_zpack.lua'), tree, inp, mode,
                            str(seed), '1'], stdout=f, stderr=subprocess.PIPE, text=True, env=env, timeout=300)
    if p.returncode:
        with open(out, 'a') as f:
            f.write(f'ERROR run_zpack exit {p.returncode}: {p.stderr.strip()[:300]}\n')


def run_lazy(cfg, nvim, lv, seed, out):
    p = subprocess.run([nvim, '-u', 'NONE', '-l', os.path.join(config.LUA, 'run_lazy.lua'), lv, 'subset', str(seed)],
                       capture_output=True, text=True, env=dict(os.environ, LAZY=cfg['lazy']), timeout=300)
    with open(out, 'w') as f:
        f.write('\n'.join(sorted({x for x in p.stdout.splitlines() if x and not x.startswith('X')})) + '\n')


def norm(path):
    """run_zpack output in run_lazy's shape: plugin names and name -> name edges."""
    names, edges, out = {}, [], set()
    for line in open(path):
        parts = line.split()
        if line.startswith('P '):
            names[parts[2][4:]] = parts[1]
            out.add('P ' + parts[1])
        elif line.startswith('E '):
            edges.append((parts[1], parts[3]))
    for a, b in edges:
        if a in names and b in names:
            out.add(f'E {names[a]} -> {names[b]}')
    return out


def lines(path, opts):
    return [x.rstrip('\n') for x in open(path) if x.startswith('O ') == opts]


def lazy_map(path):
    out = {}
    for x in open(path):
        if x.startswith('P '):
            p = x.split()
            out[p[1]] = p[-1]
    return out


def flips(a, b):
    ma, mb = lazy_map(a), lazy_map(b)
    return sorted(f'{n}: {ma[n]} -> {mb[n]}' for n in ma.keys() & mb.keys() if ma[n] != mb[n])


def changed(a, b, opts=False):
    la, lb = collections.Counter(lines(a, opts)), collections.Counter(lines(b, opts))
    return [f'< {x}' for x in sorted((la - lb).elements())] + [f'> {x}' for x in sorted((lb - la).elements())]


def errors(path):
    return [x.strip() for x in open(path) if x.startswith(('ERROR', 'CONFLICT', 'MODFAIL'))]


def new_errors(a, b):
    return sorted(set(errors(b)) - set(errors(a)))


def tokens(line):
    return sorted(line.replace('{', ',').replace('}', ',').split(','))


def opts_split(a, b):
    """Changed O lines, and how many plugins changed only in list order (same tokens)."""
    ch = changed(a, b, True)
    old = {x.split()[1]: x[2:] for x in ch if x[0] == '<'}
    new = {x.split()[1]: x[2:] for x in ch if x[0] == '>'}
    order = {n for n in old.keys() & new.keys() if tokens(old[n]) == tokens(new[n])}
    return ch, order


def run(cfg, base, refs, seeds, oracle, nvim_name, jobs=6):
    nvim = config.nvim(cfg, nvim_name)
    lv = lazyvim_dir(cfg)
    live = live_sandbox(cfg)
    live_env = sandbox.env_for(live)
    out_dir = os.path.join(cfg['work'], 'diff', 'out')
    shutil.rmtree(out_dir, ignore_errors=True)
    labels = []
    jobs_list = []
    for ref in [base] + refs:
        label = trees.label(cfg, ref)
        tree = trees.build(cfg, ref)
        labels.append(label)
        d = os.path.join(out_dir, label)
        os.makedirs(f'{d}/sub')
        jobs_list.append((tree, lv, 'all', 0, f'{d}/all.txt', None))
        jobs_list.append((tree, f'{live}/live.lua', 'file', 0, f'{d}/live.txt', live_env))
        jobs_list += [(tree, lv, 'subset', s, f'{d}/sub/{s}.txt', None) for s in range(1, seeds + 1)]
    with ThreadPoolExecutor(jobs) as ex:
        list(ex.map(lambda j: run_zpack(cfg, nvim, *j), jobs_list))

    path = lambda label, name: os.path.join(out_dir, label, name)
    subs = [f'sub/{s}.txt' for s in range(1, seeds + 1)]
    b = labels[0]
    print(f"LazyVim {open(os.path.join(os.path.dirname(lv), 'SHA')).read().strip()[:12]}, {seeds} subsets, "
          f"live config {cfg['user_config']}, nvim {nvim_name}")
    for label in labels:
        print(f"  {label}: all P={len(lazy_map(path(label, 'all.txt')))} "
              f"lazy={sum(v == 'lazy=true' for v in lazy_map(path(label, 'all.txt')).values())} | "
              f"live P={len(lazy_map(path(label, 'live.txt')))} "
              f"lazy={sum(v == 'lazy=true' for v in lazy_map(path(label, 'live.txt')).values())}")
    clean = True
    for r in labels[1:]:
        print(f'\n## {b} vs {r}')
        fl = {n: flips(path(b, n), path(r, n)) for n in ['all.txt', 'live.txt'] + subs}
        nflips = sum(len(v) for v in fl.values())
        print(f'  lazy= flips: {nflips}' + ('  !!' if nflips else ''))
        for n, v in fl.items():
            for x in v:
                print(f'    {n}: {x}')
        opts_total = 0
        for n in ('all.txt', 'live.txt'):
            st, er = changed(path(b, n), path(r, n)), new_errors(path(b, n), path(r, n))
            op, order = opts_split(path(b, n), path(r, n))
            opts_total += len(op)
            print(f'  {n[:-4]}: structural={len(st)} opts={len(op) // 2} plugins ({len(order)} order-only) '
                  f'new errors={len(er)}')
            for x in st[:40] + er[:10] + [f'opts: {o}' for o in sorted({x.split()[2] for x in op})]:
                print(f'    {x}')
            clean = clean and not st and not er
        cnt = collections.Counter(x for s in subs for x in changed(path(b, s), path(r, s)) if x[2] in 'PEW')
        sub_err = sum(len(new_errors(path(b, s), path(r, s))) for s in subs)
        sub_opts = [opts_split(path(b, s), path(r, s)) for s in subs]
        n_opts = sum(len(o) for o, _ in sub_opts) // 2
        n_order = sum(len(x) for _, x in sub_opts)
        print(f'  subsets: distinct differing P/E/W lines={len(cnt)} opts={n_opts} plugin-subsets ({n_order} order-only) '
              f'new errors={sub_err}')
        for x, c in sorted(cnt.items()):
            print(f'    {c:3d} {x}')
        clean = clean and not nflips and not cnt and not sub_err
        print(f'  VERDICT {r}: {nflips} lazy= flips, '
              + ('no structural changes or new errors' if clean else 'structural changes or new errors above')
              + (f'; opts changed ({opts_total // 2 + n_opts}), see above' if opts_total or n_opts else ''))
    if oracle:
        last = labels[-1]
        print(f'\n## lazy.nvim oracle vs {last} (subsets; < lazy.nvim only, > zpack only)')
        with ThreadPoolExecutor(jobs) as ex:
            list(ex.map(lambda s: run_lazy(cfg, nvim, lv, s, path(last, f'sub/{s}.lazy')), range(1, seeds + 1)))
        cnt = collections.Counter()
        for s in range(1, seeds + 1):
            lz = {x.strip() for x in open(path(last, f'sub/{s}.lazy')) if x.strip()}
            zp = norm(path(last, f'sub/{s}.txt'))
            cnt.update([f'< {x}' for x in lz - zp] + [f'> {x}' for x in zp - lz])
        expr = sum(c for x, c in cnt.items() if '<expr>' in x)
        for x, c in sorted(cnt.items()):
            if '<expr>' not in x:
                print(f'    {c:3d} {x}')
        print(f'    <expr> lines (parser placeholder, ignore): {expr}')
    print(f'\noutputs: {out_dir}')
    return clean
