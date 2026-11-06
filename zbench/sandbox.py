"""Per-row sandboxes: isolated XDG dirs holding an APFS clone of a plugin store and a scenario config."""
import os
import re
import shutil
import subprocess

from . import gen

SCENARIOS = {
    'realistic': ('realistic', 'store', None, False),
    'file': ('realistic', 'store', None, True),
    'eager': ('eager', 'store', None, False),
    'cs': ('cs', 'store', None, False),
    'inits': ('inits', 'store', None, False),
    'inits10': ('inits10', 'store', None, False),
    'trig': ('trig', 'store', None, False),
    'trig10': ('trig10', 'store', None, False),
    'ftd': ('ftd', 'store-ftd', None, False),
    'fton': ('ftd', 'store-ftd', 'filetype plugin indent on', False),
    'miss': ('miss', 'store', None, False),
}
MATRIX = ['realistic', 'file', 'eager', 'cs', 'inits', 'trig', 'trig10', 'ftd', 'fton']
MODES = ('vimenter', 'plugin')
ROW = re.compile(r'^([a-z]+?(?:10)?)_?(\d+)(?:@(\w+))?$')
QUIT = ['-c', 'doautocmd <nomodeline> UIEnter',
        '-c', "lua vim.schedule(function() vim.schedule(function() vim.cmd('qa!') end) end)"]
SETUP = "require('zpack').setup({ defaults = { confirm = false } })"


class Row:
    def __init__(self, text):
        m = ROW.match(text)
        if not m or m.group(1) not in SCENARIOS or (m.group(3) and m.group(3) not in MODES):
            raise SystemExit(f'bad row {text!r}: <scenario><n>[@vimenter|@plugin], scenarios {sorted(SCENARIOS)}')
        self.text, self.scenario, self.n, self.mode = text, m.group(1), int(m.group(2)), m.group(3)
        self.config, self.store, self.pre, self.file = SCENARIOS[self.scenario]


def expand(spec):
    rows = []
    for part in spec.split(','):
        if part in ('all', 'matrix'):
            rows += [f'{s}{"_" if s[-1].isdigit() else ""}{n}' for n in (150, 300) for s in MATRIX]
            if part == 'all':
                rows += ['miss150', 'miss300', 'realistic150@vimenter', 'realistic150@plugin']
        elif part == 'default':
            rows += ['realistic150', 'file150', 'inits150', 'trig150']
        else:
            rows.append(part)
    return [Row(r) for r in rows]


def env_for(root):
    return dict(os.environ, **{f'XDG_{k}_HOME': f'{root}/{k.lower()}' for k in ('CONFIG', 'DATA', 'STATE', 'CACHE')})


def clone(src, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    subprocess.run(['cp', '-cR', src, dest], check=True)


def ensure(cfg, row, kind, seed=1):
    """Sandbox for one manager on one row; shared by every tree of that manager."""
    sdir = gen.set_dir(cfg, row.n, seed)
    root = os.path.join(cfg['work'], 'sand', f'n{row.n}-s{seed}', row.config + (f'-{row.store}' if row.store != 'store' else '')
                        + (f'@{row.mode}' if row.mode else ''), kind)
    if os.path.isdir(root):
        return root, sdir
    tmp = root + '.tmp'
    shutil.rmtree(tmp, ignore_errors=True)
    store = f'{sdir}/{row.store}.noindex'
    lock = f'{sdir}/lock{"-ftd" if row.store == "store-ftd" else ""}.json'
    if kind in ('zpack', 'native'):
        clone(store, f'{tmp}/data/nvim/site/pack/core/opt')
        os.makedirs(f'{tmp}/config/nvim', exist_ok=True)
        shutil.copy(lock, f'{tmp}/config/nvim/nvim-pack-lock.json')
    elif kind == 'lazy':
        clone(store, f'{tmp}/data/nvim/lazy')
    if kind in ('zpack', 'lazy'):
        shutil.copytree(f'{sdir}/configs/{row.config}/plugins', f'{tmp}/config/nvim/lua/plugins')
    if row.mode == 'plugin' and kind == 'zpack':
        gen.write(f'{tmp}/config/nvim/plugin/zpack.lua', f'vim.opt.rtp:prepend(vim.g.zb_tree)\n{SETUP}\n')
    os.makedirs(f'{tmp}/config/nvim', exist_ok=True)
    os.rename(tmp, root)
    return root, sdir


def init_text(cfg, row, kind, tree, root):
    pre = f'vim.cmd({row.pre!r})\n' if row.pre and kind in ('zpack', 'lazy') else ''
    if kind == 'bare':
        return ''
    if kind == 'native':
        names = sorted(os.listdir(f'{root}/data/nvim/site/pack/core/opt'))
        items = ', '.join(f"{{ src = '{gen.URL}{n}', name = '{n}' }}" for n in names)
        return f'vim.loader.enable()\nvim.pack.add({{ {items} }}, {{ confirm = false }})\n'
    if kind == 'lazy':
        return pre + f"""vim.opt.rtp:prepend('{cfg['lazy']}')
require('lazy').setup({{ spec = {{ {{ import = 'plugins' }} }}, install = {{ missing = false }},
  change_detection = {{ enabled = false }}, checker = {{ enabled = false }}, rocks = {{ enabled = false }} }})
"""
    if row.mode == 'plugin':
        return pre + f'vim.g.zb_tree = {tree!r}\n'
    body = f'vim.opt.rtp:prepend({tree!r})\n{SETUP}\n'
    if row.mode == 'vimenter':
        body = f"vim.api.nvim_create_autocmd('VimEnter', {{ once = true, callback = function()\n{body}end }})\n"
    return pre + body


def command(cfg, nvim, row, target, seed=1):
    """target: (label, kind, tree or None). Returns (argv, env)."""
    label, kind, tree = target
    root, sdir = ensure(cfg, row, kind, seed)
    init = f'{root}/init-{label}.lua'
    gen.write(init, init_text(cfg, row, kind, tree, root))
    args = [nvim, '--headless', '-i', 'NONE', '-u', init]
    if row.file:
        args.append(f'{sdir}/sample.rs')
    return args + QUIT, env_for(root)
