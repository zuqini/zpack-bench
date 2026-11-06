"""In-process import+resolve timing and jit.profile sampling of real startups."""
import collections
import os
import subprocess

from . import config, diff, sandbox, trees


def inproc(cfg, refs, inp, rounds, nvim_name):
    """Import + resolve_all per tree in one process, rotating order each round."""
    nvim = config.nvim(cfg, nvim_name)
    names = [os.path.basename(trees.build(cfg, r)) for r in refs]
    if inp == 'live':
        root = diff.live_sandbox(cfg)
        root_arg, mode, env = f'{root}/live.lua', 'file', sandbox.env_for(root)
    else:
        root_arg, mode, env = diff.lazyvim_dir(cfg), inp, sandbox.env_for(diff.empty_sandbox(cfg))
    subprocess.run([nvim, '-u', 'NONE', '-l', os.path.join(config.LUA, 'inproc.lua'),
                    os.path.join(cfg['work'], 'trees'), root_arg, mode, str(rounds), *names], check=True, env=env,
                   cwd=sandbox.cwd(env))


def sprof(cfg, ref, row, runs, top, nvim_name):
    """Aggregate jit.profile samples over fresh startups of one row; ms per startup."""
    nvim = config.nvim(cfg, nvim_name)
    target = (trees.label(cfg, ref), 'zpack', trees.build(cfg, ref))
    out = os.path.join(cfg['work'], 'out', 'sprof.tsv')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    start = os.path.join(config.LUA, 'sprof_start.lua')
    args, env = sandbox.command(cfg, nvim, row, target, prefix=f'dofile({start!r})\n')
    env['SPROF_OUT'] = out
    for i in range(runs + 3):
        if i == 3 and os.path.exists(out):
            os.unlink(out)
        subprocess.run(args, env=env, cwd=sandbox.cwd(env), stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
    self_l, incl, vms, jl = (collections.Counter() for _ in range(4))
    total = 0
    for row_ in open(out):
        p = row_.rstrip('\n').split('\t')
        if len(p) < 4:
            continue
        c = int(p[0])
        total += c
        vms[p[1]] += c
        self_l[p[3]] += c
        if p[1] == 'J':
            jl[p[3]] += c
        for fr in set(p[2].split('|')):
            if fr:
                incl[fr] += c
    print(f'{row.text} {ref}: samples/startup {total / runs:.1f} ms  vm: '
          + ' '.join(f'{k}={v / runs:.1f}' for k, v in vms.most_common()))
    for title, counter, n in (('inclusive by function', incl, top), ('JIT compiler time by line', jl, 30),
                              ('self by line', self_l, top)):
        print(f'-- {title} (ms/startup)')
        for k, v in counter.most_common(n):
            print(f'{v / runs:7.2f}  {k}')
