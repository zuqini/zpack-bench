import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LUA = os.path.join(ROOT, 'lua')


def _expand(v):
    if isinstance(v, str):
        return os.path.expanduser(v)
    if isinstance(v, dict):
        return {k: _expand(x) for k, x in v.items()}
    return v


def load():
    cfg = json.load(open(os.path.join(ROOT, 'config.json')))
    local = os.path.join(ROOT, 'local.json')
    if os.path.exists(local):
        cfg.update(json.load(open(local)))
    for key in ('lazy', 'zpack_repo', 'user_config', 'user_data', 'work'):
        env = os.environ.get('ZB_' + key.upper())
        if env:
            cfg[key] = env
    cfg = _expand(cfg)
    work = cfg['work']
    cfg['work'] = work if os.path.isabs(work) else os.path.join(ROOT, work)
    os.makedirs(cfg['work'], exist_ok=True)
    # Symlinked paths would make sandboxes link back to the real config instead of cloning it.
    for key in ('lazy', 'zpack_repo', 'user_config', 'user_data', 'work'):
        cfg[key] = os.path.realpath(cfg[key])
    return cfg


def nvim(cfg, name):
    return cfg['nvim'].get(name, name)
