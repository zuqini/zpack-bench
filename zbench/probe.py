"""Real-config probe: start a real config with XDG isolated, dump its state per tree, diff the trees."""
import collections
import difflib
import os
import shutil
import subprocess

from . import config, perf, sandbox, trees

SAMPLE = 'fn main() {}\n'


def make_sandbox(cfg, cfg_dir):
    root = os.path.join(cfg['work'], 'probe', 'sand.noindex')
    shutil.rmtree(root, ignore_errors=True)
    sandbox.clone(cfg_dir, f'{root}/config/nvim')
    if os.path.isdir(cfg['user_data']):
        sandbox.clone(cfg['user_data'], f'{root}/data/nvim')
    with open(f'{root}/sample.rs', 'w') as f:
        f.write(SAMPLE)
    return root


def argv(nvim, root, tree, mode, probe):
    a = [nvim, '--headless', '-i', 'NONE', '--cmd', f'set rtp^={tree}']
    if mode == 'file':
        a.append(f'{root}/sample.rs')
    tail = ['-c', f"lua dofile({os.path.join(config.LUA, 'probe.lua')!r})"] if probe else sandbox.QUIT[2:]
    return a + ['-c', 'doautocmd <nomodeline> UIEnter'] + tail


def dump(nvim, root, tree, mode, out):
    env = dict(sandbox.env_for(root), ZB_OUT=out, ZB_TREE=tree)
    p = subprocess.run(argv(nvim, root, tree, mode, True), env=env, cwd=root, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=120)
    err = ' '.join(p.stderr.split())
    if p.returncode or not os.path.exists(out):
        err = f'exit {p.returncode}, no dump. {err}'
    return err


def sections(path):
    out, cur = collections.OrderedDict(), None
    for line in open(path):
        line = line.rstrip('\n')
        if line.startswith('== '):
            cur = line[3:]
            out[cur] = []
        elif cur:
            out[cur].append(line)
    return out


def run(cfg, refs, cfg_dir, reps, nvim_name):
    nvim = config.nvim(cfg, nvim_name)
    root = make_sandbox(cfg, cfg_dir)
    targets = [(trees.label(cfg, r), trees.build(cfg, r)) for r in refs]
    out_dir = os.path.join(cfg['work'], 'probe', 'out')
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir)
    for _, tree in targets:
        for mode in ('nofile', 'file'):
            for _ in range(3):
                perf.once(argv(nvim, root, tree, mode, False), sandbox.env_for(root))
    clean = True
    for mode in ('nofile', 'file'):
        print(f'## {mode}: {cfg_dir}, nvim {nvim_name}, {reps} reps per tree')
        dumps, errs = {}, collections.defaultdict(list)
        for label, tree in targets:
            dumps[label] = []
            for rep in range(reps):
                out = os.path.join(out_dir, f'{mode}.{label}.{rep}.txt')
                err = dump(nvim, root, tree, mode, out)
                if err:
                    errs[err].append(f'{label}#{rep}')
                dumps[label].append(sections(out) if os.path.exists(out) else {})
        base = targets[0][0]
        for err, where in errs.items():
            new = [w for w in where if not w.startswith(base + '#')] and not any(w.startswith(base + '#') for w in where)
            print(f"  {'!! new ' if new else ''}stderr in {len(where)}/{reps * len(targets)} runs "
                  f"({', '.join(where)}): {err[:300]}")
            clean = clean and not new
        missing = [f'{label}#{i}' for label in dumps for i, d in enumerate(dumps[label]) if not d]
        if missing:
            print(f"  !! no dump from {', '.join(missing)}")
            clean = False
        names = []
        for d in (d for ds in dumps.values() for d in ds):
            names += [n for n in d if n not in names]
        for name in names:
            unstable = [label for label in dumps if any(d.get(name) != dumps[label][0].get(name) for d in dumps[label])]
            differs = [label for label in dumps if label != base and dumps[label][0].get(name) != dumps[base][0].get(name)]
            state = 'same' if not differs else 'DIFFERS'
            note = f" (varies between reps: {', '.join(unstable)})" if unstable else ''
            print(f'  {name:<11} {state}{note}')
            if differs and name != 'ZPACK_MODS':
                clean = False
            for label in differs:
                a, b = dumps[base][0].get(name, []), dumps[label][0].get(name, [])
                lines = [x for x in difflib.unified_diff(a, b, base, label, n=0, lineterm='') if x[:1] in '+-'
                         and not x.startswith(('+++', '---'))]
                for x in lines[:30]:
                    print(f'      {x[:200]}')
                if len(lines) > 30:
                    print(f'      ... {len(lines)} lines')
    print(f'outputs: {out_dir}')
    print('VERDICT: identical state' if clean else 'VERDICT: state differs (see above)')
    return clean
