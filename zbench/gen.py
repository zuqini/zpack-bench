"""Synthetic plugin sets: one store of git repos per (n, seed) plus a lua/plugins config per scenario.

The base set keeps the RNG call order of the 2026-10-30 bench gen.py, so seed 1 reproduces its specs.
Scenario transforms are rules over the base kinds; the few choices they make use their own RNG.
"""
import json
import os
import random
import shutil
import subprocess

SCENARIOS = ('realistic', 'eager', 'cs', 'inits', 'inits10', 'trig', 'trig10', 'ftd', 'miss')
URL = 'https://example.invalid/bench/'
GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME='b', GIT_AUTHOR_EMAIL='b@b', GIT_COMMITTER_NAME='b',
               GIT_COMMITTER_EMAIL='b@b', GIT_AUTHOR_DATE='2026-01-01T00:00:00Z',
               GIT_COMMITTER_DATE='2026-01-01T00:00:00Z')
TRIGGER_KINDS = ('event', 'verylazy', 'cmd', 'keys', 'ft')
FTD_COUNT = 40


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(text)


def git(*args):
    subprocess.run(['git', *args], check=True, env=GIT_ENV, capture_output=True)


def commit(d, msg):
    git('-C', d, 'add', '-A')
    git('-C', d, 'commit', '-qm', msg)
    return subprocess.run(['git', '-C', d, 'rev-parse', 'HEAD'], check=True, capture_output=True,
                          text=True).stdout.strip()


def body(mod, lines):
    fns = '\n'.join(f"function M.f{i}(a, b)\n  local t = {{ a = a, b = b, i = {i} }}\n  return t.a or t.b or t.i\nend"
                    for i in range(lines // 4))
    return f"local M = {{ name = '{mod}' }}\n{fns}\nreturn M\n"


class Plugin:
    def __init__(self, i, kind):
        self.i, self.kind = i, kind
        self.name = f'bench{i:03d}.nvim'
        self.mod = f'bench{i:03d}'
        self.trigger = []
        self.deps = None

    def spec(self, trigger=None, extra=()):
        fields = [f"url = '{URL}{self.name}'", f"name = '{self.name}'", *extra]
        fields += self.trigger if trigger is None else trigger
        if self.deps:
            fields.append(self.deps)
        return '{ ' + ', '.join(fields) + ' }'


def base(store, n, seed):
    """Build the git repos and base specs. Same RNG call order as the original gen.py."""
    rng = random.Random(seed)
    kinds = ['eager'] * 30 + ['event'] * 30 + ['verylazy'] * 10 + ['cmd'] * 25 + ['ft'] * 15 + ['keys'] * 20 + ['dep'] * 20
    kinds = (kinds * (n // len(kinds) + 1))[:n]
    rng.shuffle(kinds)
    plugins = [Plugin(i, k) for i, k in enumerate(kinds)]
    deps = [p.name for p in plugins if p.kind == 'dep']
    locks = {}
    for p in plugins:
        d, mod, i = f'{store}/{p.name}', p.mod, p.i
        subs = rng.randint(2, 12)
        reqs = ''.join(f"M.s{j} = require('{mod}.s{j}')\n" for j in range(min(subs, 3)))
        write(f'{d}/lua/{mod}/init.lua',
              f"local M = {{ opts = nil }}\n{reqs}function M.setup(o) M.opts = o; vim.g.{mod}_setup = true end\nreturn M\n")
        for j in range(subs):
            write(f'{d}/lua/{mod}/s{j}.lua', body(f'{mod}.s{j}', rng.randint(40, 400)))
        write(f'{d}/README.md', f'# {p.name}\n')
        write(f'{d}/doc/{mod}.txt', f'*{mod}.txt*\n\n vim:ft=help\n')
        if rng.random() < .5:
            write(f'{d}/plugin/{mod}.lua',
                  f"vim.g.loaded_{mod} = 1\nvim.api.nvim_create_user_command('Bench{i:03d}Cmd', function() require('{mod}') end, {{}})\n")
        if rng.random() < .1:
            write(f'{d}/after/plugin/{mod}.lua', f'vim.g.after_{mod} = 1\n')
        if rng.random() < .1:
            write(f'{d}/ftdetect/{mod}.lua', f"vim.filetype.add({{ extension = {{ {mod} = '{mod}' }} }})\n")
        if rng.random() < .1:
            write(f'{d}/ftplugin/{mod}.lua', f'vim.b.{mod} = 1\n')
        if i == 0:
            write(f'{d}/colors/{mod}.lua',
                  f"vim.cmd('hi clear')\nvim.g.colors_name = '{mod}'\nvim.api.nvim_set_hl(0, 'Normal', {{ fg = '#c0c0c0', bg = '#101010' }})\n")
        git('init', '-q', '-b', 'main', d)
        rev = commit(d, 'init')
        git('-C', d, 'remote', 'add', 'origin', URL + p.name)
        locks[p.name] = {'rev': rev, 'src': URL + p.name}
        k = p.kind
        if k == 'eager':
            p.trigger = ['lazy = false', 'opts = { a = 1, nested = { b = 2 } }']
        elif k == 'event':
            p.trigger = [f"event = '{rng.choice(['BufReadPre', 'BufReadPost', 'InsertEnter', 'BufNewFile'])}'", 'opts = {}']
        elif k == 'verylazy':
            p.trigger = ["event = 'VeryLazy'", 'opts = {}']
        elif k == 'cmd':
            p.trigger = [f"cmd = {{ 'BenchLazy{i:03d}' }}", 'opts = {}']
        elif k == 'ft':
            p.ft = rng.choice(['rust', 'python', 'go', 'markdown', 'zig'])
            p.trigger = [f"ft = {{ '{p.ft}' }}", 'opts = {}']
        elif k == 'keys':
            p.keys = f"{{ {{ '<leader>b{i:03d}', function() end, desc = 'b{i}' }} }}"
            p.trigger = [f'keys = {p.keys}', 'opts = {}']
        else:
            p.trigger = ['lazy = true']
        if k != 'dep' and rng.random() < .3 and deps:
            p.deps = 'dependencies = { ' + ', '.join(
                f"{{ url = '{URL}{x}', name = '{x}', lazy = true }}" for x in rng.sample(deps, rng.randint(1, 3))) + ' }'
    return plugins, locks


def eager_spec(s):
    s = s.replace('lazy = true', 'lazy = false')
    return s if ', lazy = false' in s.split(', dependencies')[0] else s[:-2] + ', lazy = false }'


def init_fn(p):
    m = f'bench_missing_{p.i:03d}'
    return f"init = function() vim.g.bench_init_{p.i:03d} = 1; pcall(require, '{m}_a'); pcall(require, '{m}_b') end"


def trig_set(plugins):
    return [p for p in plugins if p.i % 2 == 0 and p.kind in ('cmd', 'keys', 'ft')]


def trig_trigger(p, eager_mod):
    if p.kind == 'keys':
        return [f'keys = function(_, keys) require({p.mod!r}); return {p.keys} end', 'opts = {}']
    if p.kind == 'cmd':
        return [f"cmd = function() pcall(require, 'bench_missing_c{p.i:03d}'); return {{ 'BenchLazy{p.i:03d}' }} end", 'opts = {}']
    return [f"ft = function() pcall(require, '{eager_mod}'); return {{ '{p.ft}' }} end", 'opts = {}']


def ftd_set(plugins):
    ft = [p for p in plugins if p.kind == 'ft'][:FTD_COUNT]
    rest = [p for p in plugins if p.kind in TRIGGER_KINDS and p.kind != 'ft'][:FTD_COUNT - len(ft)]
    return sorted(ft + rest, key=lambda p: p.i)


def specs(plugins, scenario, seed):
    rng = random.Random(f'{seed}:{scenario}')
    out = {}
    if scenario == 'realistic':
        return {p.i: p.spec() for p in plugins}
    if scenario in ('eager', 'cs'):
        out = {p.i: eager_spec(p.spec()) for p in plugins}
        if scenario == 'cs':
            out[0] = plugins[0].spec(['lazy = false', 'priority = 1000',
                                      "config = function() vim.cmd.colorscheme('bench000') end"])
            if plugins[0].deps:
                out[0] = out[0].replace(', ' + plugins[0].deps, '')
        return out
    out = {p.i: p.spec() for p in plugins}
    if scenario in ('inits', 'inits10'):
        chosen = [p for p in plugins if p.i % 3 == 0]
        for p in chosen[:10] if scenario == 'inits10' else chosen:
            out[p.i] = p.spec(extra=[init_fn(p)])
    elif scenario in ('trig', 'trig10'):
        rng = random.Random(f'{seed}:trig')
        eager = [p.mod for p in plugins if p.kind == 'eager']
        chosen = trig_set(plugins)
        picks = {p.i: rng.choice(eager) for p in chosen if p.kind == 'ft'}
        if scenario == 'trig10':
            chosen = ([p for p in chosen if p.kind == 'keys'][:4] + [p for p in chosen if p.kind == 'cmd'][:3]
                      + [p for p in chosen if p.kind == 'ft'][:3])
        for p in chosen:
            out[p.i] = p.spec(trig_trigger(p, picks.get(p.i)))
    elif scenario == 'ftd':
        for p in ftd_set(plugins):
            out[p.i] = p.spec([f"ft = {{ 'ftd{p.i:03d}' }}", 'opts = {}'])
    elif scenario == 'miss':
        for p in plugins[:2 * len(plugins) // 3]:
            probe = f"config = function() for k = 1, 3 do pcall(require, 'bench_miss_{p.i:03d}_' .. k) end end"
            out[p.i] = p.spec(['lazy = false', probe])
    return out


def write_config(cfg_dir, out):
    shutil.rmtree(cfg_dir, ignore_errors=True)
    items = [out[i] for i in sorted(out)]
    per = 8
    for idx in range(0, len(items), per):
        text = ',\n'.join('  ' + s for s in items[idx:idx + per])
        write(f'{cfg_dir}/plugins/group{idx // per:02d}.lua', f'return {{\n{text},\n}}\n')


def ftd_store(store, ftd, plugins, locks):
    subprocess.run(['cp', '-cR', store, ftd], check=True)
    locks = json.loads(json.dumps(locks))
    for pos, p in enumerate(ftd_set(plugins)):
        d, ft = f'{ftd}/{p.name}', f'ftd{p.i:03d}'
        if pos % 2 == 0:
            write(f'{d}/ftdetect/{ft}.vim', f'au BufRead,BufNewFile *.{ft} set filetype={ft}\n')
        else:
            write(f'{d}/ftdetect/{ft}.lua', f"vim.filetype.add({{ extension = {{ {ft} = '{ft}' }} }})\n")
        write(f'{d}/ftplugin/{ft}.vim', f'let b:{ft} = 1\n')
        locks[p.name]['rev'] = commit(d, 'ftd')
    return locks


def generate(set_dir, n, seed):
    """Create <set_dir>/{store.noindex,store-ftd.noindex,lock*.json,configs/<scenario>/plugins}."""
    stamp = f'{set_dir}/.done'
    if os.path.exists(stamp):
        return set_dir
    shutil.rmtree(set_dir, ignore_errors=True)
    os.makedirs(set_dir)
    store, ftd = f'{set_dir}/store.noindex', f'{set_dir}/store-ftd.noindex'
    plugins, locks = base(store, n, seed)
    json.dump({'plugins': locks}, open(f'{set_dir}/lock.json', 'w'), indent=2, sort_keys=True)
    ftd_locks = ftd_store(store, ftd, plugins, locks)
    json.dump({'plugins': ftd_locks}, open(f'{set_dir}/lock-ftd.json', 'w'), indent=2, sort_keys=True)
    for scenario in SCENARIOS:
        write_config(f'{set_dir}/configs/{scenario}', specs(plugins, scenario, seed))
    write(f'{set_dir}/sample.rs', 'fn main() {}\n')
    kinds = {}
    for p in plugins:
        kinds[p.kind] = kinds.get(p.kind, 0) + 1
    json.dump({'n': n, 'seed': seed, 'kinds': kinds}, open(stamp, 'w'))
    return set_dir


def set_dir(cfg, n, seed):
    return generate(os.path.join(cfg['work'], 'sets', f'n{n}-s{seed}'), n, seed)
