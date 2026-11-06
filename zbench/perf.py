"""Cross-process startup bench: shuffled paired rounds, d-cpu medians with bootstrap CIs, load checks."""
import json
import os
import random
import resource
import statistics as st
import subprocess
import sys
import time

from . import config, sandbox, stats, trees

WARMUP = 5
TIMEOUT = 60


def load1():
    return os.getloadavg()[0]


def wait_quiet(max_load, log=sys.stderr):
    waited = 0
    while load1() > max_load:
        if waited % 60 == 0:
            log.write(f'  waiting for load {load1():.1f} <= {max_load}\n')
        time.sleep(5)
        waited += 5


def once(args, env):
    """One startup. Returns (wall ms, cpu ms, error text or '')."""
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    t = time.perf_counter()
    p = subprocess.Popen(args, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.PIPE, text=True)
    try:
        _, err = p.communicate(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        p.kill()
        p.communicate()
        err = f'timeout after {TIMEOUT}s'
    wall = (time.perf_counter() - t) * 1e3
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (after.ru_utime - before.ru_utime + after.ru_stime - before.ru_stime) * 1e3
    if p.returncode and not err.strip():
        err = f'exit {p.returncode}'
    return wall, cpu, err.strip()


def targets_for(cfg, refs, base, extra, row):
    out = []
    for i, ref in enumerate(refs):
        out.append((trees.label(cfg, ref), 'zpack', trees.build(cfg, ref)))
        if i == 0 and 'aa' in extra:
            out.append((trees.label(cfg, ref) + '_aa', 'zpack', trees.build(cfg, ref, aa=True)))
    if base:
        out.append((trees.label(cfg, base), 'zpack', trees.build(cfg, base)))
    for kind in ('lazy', 'bare', 'native'):
        if kind in extra and not (row.mode and kind == 'lazy'):
            out.append((kind, kind, None))
    return out


SANITY = ("lua vim.schedule(function() vim.schedule(function() io.stderr:write(('ZB setups=%d colors=%s\\n')"
          ":format(#vim.fn.getcompletion('g:bench', 'var'), vim.g.colors_name or '')) vim.cmd('qa!') end) end)")


def sanity(args, env):
    """How many plugins ran setup() (vim.g.benchNNN_setup), from one extra startup."""
    p = subprocess.run(args[:-1] + [SANITY], env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                       timeout=TIMEOUT)
    line = [x for x in p.stderr.splitlines() if x.startswith('ZB ')]
    return line[0][3:] if line else 'no report: ' + p.stderr.strip()[:200]


def run_row(cfg, nvim_name, row, targets, rounds, seed):
    nvim = config.nvim(cfg, nvim_name)
    cmds = {t[0]: sandbox.command(cfg, nvim, row, t) for t in targets}
    names = [t[0] for t in targets]
    errors = {n: [] for n in names}
    seen = {n: sanity(*cmds[n]) for n in names}
    for n in names:
        for _ in range(WARMUP):
            once(*cmds[n])
    cpu = {n: [] for n in names}
    wall = {n: [] for n in names}
    rng = random.Random(seed)
    load_start = load1()
    for _ in range(rounds):
        order = names[:]
        rng.shuffle(order)
        for n in order:
            w, c, e = once(*cmds[n])
            cpu[n].append(c)
            wall[n].append(w)
            if e:
                errors[n].append(e)
    main = names[0]
    deltas = {n: stats.paired(cpu[main], cpu[n], seed) for n in names[1:]}
    return {
        'row': row.text, 'nvim': nvim_name, 'rounds': rounds, 'seed': seed,
        'load': [round(load_start, 2), round(load1(), 2)], 'main': main,
        'cpu_median': {n: round(st.median(cpu[n]), 2) for n in names},
        'wall_median': {n: round(st.median(wall[n]), 2) for n in names},
        'd_cpu': {n: [round(x, 2) for x in d] for n, d in deltas.items()},
        'sanity': seen,
        'errors': {n: e[:3] + ([f'... {len(e)} total'] if len(e) > 3 else []) for n, e in errors.items() if e},
        'cpu': cpu,
    }


def flags(res, max_load):
    """Problems that make a row's numbers untrustworthy or a failure."""
    out = []
    if max(res['load']) > max_load:
        out.append(f'LOAD>{max_load:g}')
    if res['errors']:
        out.append('ERRORS')
    main = res['sanity'][res['main']]
    checked = {n: v for n, v in res['sanity'].items() if n not in ('bare', 'native')}
    if main.startswith('no report') or any(v != main for v in checked.values()):
        out.append('SANITY')
    lazy = res['d_cpu'].get('lazy')
    if lazy and lazy[2] > 0:
        out.append('NOT-FASTER-THAN-LAZY')
    return out


def regressions(res):
    """Base targets the main ref is slower than by more than the A/A's CI upper bound + 1 ms."""
    aa = res['d_cpu'].get(res['main'] + '_aa')
    slack = (aa[2] if aa else 0) + 1.0
    return [n for n, d in res['d_cpu'].items() if n not in ('lazy', 'bare', 'native') and not n.endswith('_aa')
            and d[1] > slack]


def print_row(res, max_load, out=sys.stdout):
    f = flags(res, max_load)
    out.write(f"{res['row']} [{res['nvim']}] {res['rounds']} rounds, load {res['load'][0]:.1f}-{res['load'][1]:.1f}"
              f"{'  !! ' + ' '.join(f) if f else ''}\n")
    for n, m in res['cpu_median'].items():
        out.write(f'  {n:<16} cpu med {m:7.2f}  wall med {res["wall_median"][n]:7.2f}  {res["sanity"][n]}\n')
    for n, d in res['d_cpu'].items():
        out.write(f"  d-cpu {res['main']} - {n:<16} {stats.fmt(*d)}\n")
    for n, errs in res['errors'].items():
        out.write(f'  !! {n}: {errs[0][:300]}\n')


def summary(results, max_load, out=sys.stdout):
    cols = []
    for r in results:
        for n in r['d_cpu']:
            if n not in cols:
                cols.append(n)
    out.write(f"\nd-cpu {results[0]['main']} minus X, ms [95% CI]\n")
    out.write('| row | nvim | load | ' + ' | '.join(cols) + ' | cpu |\n|' + '---|' * (len(cols) + 4) + '\n')
    for r in results:
        cells = [stats.fmt(*r['d_cpu'][c]).strip() if c in r['d_cpu'] else '' for c in cols]
        f = flags(r, max_load)
        out.write(f"| {r['row']} | {r['nvim']} | {r['load'][0]:.1f}-{r['load'][1]:.1f}{' ' + ' '.join(f) if f else ''} | "
                  + ' | '.join(cells) + f" | {r['cpu_median'][r['main']]:.2f} |\n")


def verdict(results, max_load):
    bad = [(r['row'] + f"[{r['nvim']}]", flags(r, max_load)) for r in results if flags(r, max_load)]
    slow = [(r['row'] + f"[{r['nvim']}]", regressions(r)) for r in results if regressions(r)]
    for row, f in bad:
        print(f"  !! {row}: {' '.join(f)}" + ('  (rerun when the machine is quiet)' if f == [f'LOAD>{max_load:g}'] else ''))
    for row, names in slow:
        print(f"  slower than {', '.join(names)} beyond the A/A + 1 ms: {row}")
    print('VERDICT: ' + ('ok' if not bad else f'FAIL ({len(bad)} of {len(results)} rows flagged)')
          + (f'; {len(slow)} rows slower than the base' if slow else ''))
    return not bad


def run(cfg, refs, base, rows, rounds, nvims, extra, seed, out_path):
    return verdict(run_rows(cfg, refs, base, rows, rounds, nvims, extra, seed, out_path), cfg['max_load'])


def run_rows(cfg, refs, base, rows, rounds, nvims, extra, seed, out_path):
    max_load = cfg['max_load']
    results = []
    for nvim_name in nvims:
        for row in rows:
            wait_quiet(max_load)
            targets = targets_for(cfg, refs, base, extra, row)
            res = run_row(cfg, nvim_name, row, targets, rounds, seed)
            results.append(res)
            print_row(res, max_load)
            sys.stdout.flush()
            json.dump(results, open(out_path, 'w'), indent=1)
    summary(results, max_load)
    print(f'raw samples: {out_path}')
    return results
