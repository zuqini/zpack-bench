"""Functional differential: LazyVim (all extras + seeded subsets) and the live config through zpack refs.

Reports lazy= flips first, then structure (P/E/W lines), opts, errors; optionally the lazy.nvim oracle.
An output that failed or holds no plugins fails the verdict: identical failures on both sides are not a pass.
"""
import collections
import glob
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

from . import config, sandbox, trees

LIVE_SPEC = "return { { import = 'plugins' } }\n"
STRUCT = ('P ', 'E ', 'W ')
FAILED = ('ERROR', 'CONFLICT', 'MODFAIL')


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


def empty_sandbox(cfg):
    """Empty XDG dirs, so LazyVim's imports never resolve against the host's real config."""
    root = os.path.join(cfg['work'], 'diff', 'empty')
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(f'{root}/config/nvim')
    return root


def run_zpack(nvim, tree, inp, mode, seed, out, env):
    with open(out, 'w') as f:
        p = subprocess.run([nvim, '-u', 'NONE', '-l', os.path.join(config.LUA, 'run_zpack.lua'), tree, inp, mode,
                            str(seed), '1'], stdout=f, stderr=subprocess.PIPE, text=True, env=env, cwd=sandbox.cwd(env),
                           timeout=300)
    if p.returncode:
        with open(out, 'a') as f:
            f.write(f'ERROR run_zpack exit {p.returncode}: {" ".join(p.stderr.split())[:300]}\n')


def run_lazy(cfg, nvim, lv, mode, seed, out, env):
    p = subprocess.run([nvim, '-u', 'NONE', '-l', os.path.join(config.LUA, 'run_lazy.lua'), lv, mode, str(seed)],
                       capture_output=True, text=True, env=dict(env, LAZY=cfg['lazy']), cwd=sandbox.cwd(env),
                       timeout=300)
    with open(out, 'w') as f:
        f.write('\n'.join(sorted({x for x in p.stdout.splitlines() if x and not x.startswith('X')})) + '\n')
        if p.returncode or not p.stdout.strip():
            f.write(f'ERROR run_lazy exit {p.returncode}: {" ".join(p.stderr.split())[:300]}\n')


def read(path):
    return [x.rstrip('\n') for x in open(path)] if os.path.exists(path) else ['ERROR missing output']


def failures(path):
    """Why an output can't be compared: a failed run, or no plugins at all."""
    lines = read(path)
    bad = [x for x in lines if x.startswith(FAILED) and not x.startswith('MODFAIL')]
    if not any(x.startswith('P ') for x in lines):
        bad.append('no P lines')
    return bad


def lazy_map(path):
    return {x.split()[1]: x.split()[-1] for x in read(path) if x.startswith('P ')}


def flips(a, b):
    ma, mb = lazy_map(a), lazy_map(b)
    return sorted(f"{n}: {ma.get(n, 'absent')} -> {mb.get(n, 'absent')}"
                  for n in ma.keys() | mb.keys() if ma.get(n) != mb.get(n))


def changed(a, b, keep):
    la = collections.Counter(x for x in read(a) if keep(x))
    lb = collections.Counter(x for x in read(b) if keep(x))
    return [f'< {x}' for x in sorted((la - lb).elements())] + [f'> {x}' for x in sorted((lb - la).elements())]


def structural(a, b):
    return changed(a, b, lambda x: x.startswith(STRUCT))


def other(a, b):
    return changed(a, b, lambda x: not x.startswith(STRUCT + ('O ',)))


TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|[{},]|[^{},"=]+=|[^{},"]+')


def canon(s):
    """run_zpack's serialised opts with every list's items sorted and keys kept with their values."""
    toks, i = TOKEN.findall(s), 0

    def value():
        nonlocal i
        t = toks[i]
        i += 1
        if t != '{':
            return t
        keyed, items = [], []
        while toks[i] != '}':
            if toks[i] == ',':
                i += 1
                continue
            if toks[i].endswith('='):
                k = toks[i]
                i += 1
                keyed.append((k, value()))
            else:
                items.append(value())
        i += 1
        return ('{', tuple(sorted(keyed, key=repr)), tuple(sorted(items, key=repr)))
    return value()


def opts(a, b):
    """Plugins whose opts differ, split into real changes and order-only ones (same canonical value)."""
    oa = {x.split()[1]: x.split(' ', 2)[2] for x in read(a) if x.startswith('O ')}
    ob = {x.split()[1]: x.split(' ', 2)[2] for x in read(b) if x.startswith('O ')}
    diff = sorted(n for n in oa.keys() | ob.keys() if oa.get(n) != ob.get(n))
    order = [n for n in diff if n in oa and n in ob and canon(oa[n]) == canon(ob[n])]
    return [n for n in diff if n not in order], order


def errors(path):
    return [x for x in read(path) if x.startswith(FAILED)]


def run(cfg, base, refs, seeds, oracle, nvim_name, jobs=6):
    nvim = config.nvim(cfg, nvim_name)
    lv = lazyvim_dir(cfg)
    live = live_sandbox(cfg)
    live_env = sandbox.env_for(live)
    lv_env = sandbox.env_for(empty_sandbox(cfg))
    out_dir = os.path.join(cfg['work'], 'diff', 'out')
    shutil.rmtree(out_dir, ignore_errors=True)
    labels = []
    jobs_list = []
    for ref in [base] + refs:
        label = trees.label(cfg, ref)
        aa = label in labels
        label, tree = label + ('_aa' if aa else ''), trees.build(cfg, ref, aa=aa)
        labels.append(label)
        d = os.path.join(out_dir, label)
        os.makedirs(f'{d}/sub')
        jobs_list.append((tree, lv, 'all', 0, f'{d}/all.txt', lv_env))
        jobs_list.append((tree, f'{live}/live.lua', 'file', 0, f'{d}/live.txt', live_env))
        jobs_list += [(tree, lv, 'subset', s, f'{d}/sub/{s}.txt', lv_env) for s in range(1, seeds + 1)]
    with ThreadPoolExecutor(jobs) as ex:
        list(ex.map(lambda j: run_zpack(nvim, *j), jobs_list))

    path = lambda label, name: os.path.join(out_dir, label, name)
    names = ['all.txt', 'live.txt'] + [f'sub/{s}.txt' for s in range(1, seeds + 1)]
    b = labels[0]
    print(f"LazyVim {open(os.path.join(os.path.dirname(lv), 'SHA')).read().strip()[:12]}, {seeds} subsets, "
          f"live config {cfg['user_config']}, nvim {nvim_name}")
    ok_all = True
    for label in labels:
        ma, ml = lazy_map(path(label, 'all.txt')), lazy_map(path(label, 'live.txt'))
        print(f"  {label}: all P={len(ma)} lazy={sum(v == 'lazy=true' for v in ma.values())} | live P={len(ml)} "
              f"lazy={sum(v == 'lazy=true' for v in ml.values())} | errors (all/live/subsets): "
              f"{len(errors(path(label, 'all.txt')))}/{len(errors(path(label, 'live.txt')))}/"
              f"{sum(len(errors(path(label, n))) for n in names[2:])}")
        bad = [(n, f) for n in names for f in failures(path(label, n))]
        for n, f in bad[:10]:
            print(f'    !! {n}: {f[:300]}')
        ok_all = ok_all and not bad
    for r in labels[1:]:
        print(f'\n## {b} vs {r}')
        fl = {n: flips(path(b, n), path(r, n)) for n in names}
        nflips = sum(len(v) for v in fl.values())
        print(f'  lazy= flips: {nflips}' + ('  !!' if nflips else ''))
        for n, v in fl.items():
            for x in v:
                print(f'    {n}: {x}')
        st = {n: structural(path(b, n), path(r, n)) for n in names}
        new_err = {n: sorted(set(errors(path(r, n))) - set(errors(path(b, n)))) for n in names}
        op = {n: opts(path(b, n), path(r, n)) for n in names}
        oth = {n: other(path(b, n), path(r, n)) for n in names}
        for n in ('all.txt', 'live.txt'):
            print(f'  {n[:-4]}: structural={len(st[n])} opts changed={len(op[n][0])} order-only={len(op[n][1])} '
                  f'new errors={len(new_err[n])} other lines={len(oth[n])}')
            for x in st[n][:40] + new_err[n][:10] + [f'opts: {o}' for o in op[n][0]] + oth[n][:10]:
                print(f'    {x[:300]}')
        subs = names[2:]
        cnt = collections.Counter(x for n in subs for x in st[n])
        sub_opts = collections.Counter(o for n in subs for o in op[n][0])
        print(f'  subsets: distinct structural lines={len(cnt)} opts changed={sum(sub_opts.values())} '
              f'order-only={sum(len(op[n][1]) for n in subs)} new errors={sum(len(new_err[n]) for n in subs)} '
              f'other lines={sum(len(oth[n]) for n in subs)}')
        for x, c in sorted(cnt.items()):
            print(f'    {c:3d} {x[:300]}')
        for o, c in sorted(sub_opts.items()):
            print(f'    {c:3d} opts: {o}')
        clean = (ok_all and not nflips and not any(st.values()) and not any(new_err.values())
                 and not any(o[0] for o in op.values()))
        ok_all = ok_all and clean
        print(f'  VERDICT {r}: ' + ('clean' if clean else 'DIFFERS') + f' ({nflips} lazy= flips, '
              f'{sum(len(v) for v in st.values())} structural, {sum(len(o[0]) for o in op.values())} opts, '
              f'{sum(len(v) for v in new_err.values())} new errors; order-only opts '
              f'{sum(len(o[1]) for o in op.values())} not counted)')
    if oracle:
        oracle_report(cfg, nvim, lv, lv_env, labels[-1], path, seeds, jobs)
    print(f'\noutputs: {out_dir}')
    return ok_all


def norm(path):
    """run_zpack output in run_lazy's shape: `P name lazy=x` and name -> name edges."""
    names, edges, out = {}, [], set()
    for line in read(path):
        parts = line.split()
        if line.startswith('P '):
            names[parts[2][4:]] = parts[1]
            out.add(f'P {parts[1]} {parts[-1]}')
        elif line.startswith('E '):
            edges.append((parts[1], parts[3]))
    for a, b in edges:
        if a in names and b in names:
            out.add(f'E {names[a]} -> {names[b]}')
    return out


def oracle_report(cfg, nvim, lv, env, last, path, seeds, jobs):
    """lazy.nvim's resolver on the same inputs; informational, it doesn't change the verdict."""
    print(f'\n## lazy.nvim oracle vs {last} (all + subsets; < lazy.nvim only, > zpack only)')
    runs = [('all', 0, 'all.lazy', 'all.txt')] + [('subset', s, f'sub/{s}.lazy', f'sub/{s}.txt')
                                                 for s in range(1, seeds + 1)]
    with ThreadPoolExecutor(jobs) as ex:
        list(ex.map(lambda r: run_lazy(cfg, nvim, lv, r[0], r[1], path(last, r[2]), env), runs))
    fl, rest, bad = collections.Counter(), collections.Counter(), []
    for _, _, lz_name, zp_name in runs:
        lz = {x for x in read(path(last, lz_name)) if x}
        bad += [f'{lz_name}: {x}' for x in lz if x.startswith('ERROR')]
        zp = norm(path(last, zp_name))
        lzm = {x.split()[1]: x.split()[2] for x in lz if x.startswith('P ')}
        zpm = {x.split()[1]: x.split()[2] for x in zp if x.startswith('P ')}
        fl.update(f'{n}: lazy.nvim {lzm[n]}, zpack {zpm[n]}' for n in lzm.keys() & zpm.keys() if lzm[n] != zpm[n])
        lz_names = {' '.join(x.split()[:2]) if x.startswith('P ') else x for x in lz if not x.startswith('ERROR')}
        zp_names = {' '.join(x.split()[:2]) if x.startswith('P ') else x for x in zp}
        rest.update([f'< {x}' for x in lz_names - zp_names] + [f'> {x}' for x in zp_names - lz_names])
    for x in bad[:5]:
        print(f'    !! {x[:300]}')
    print(f'  lazy= disagreements: {sum(fl.values())}')
    for x, c in sorted(fl.items()):
        print(f'    {c:3d} {x}')
    expr = sum(c for x, c in rest.items() if '<expr>' in x)
    print('  plugin set / edges:')
    for x, c in sorted(rest.items()):
        if '<expr>' not in x:
            print(f'    {c:3d} {x}')
    print(f'    <expr> lines (parser placeholder, ignore): {expr}')
