import os
import shutil
import subprocess


def resolve(cfg, ref):
    out = subprocess.run(['git', '-C', cfg['zpack_repo'], 'rev-parse', '--verify', ref + '^{commit}'],
                         check=True, capture_output=True, text=True)
    return out.stdout.strip()


def build(cfg, ref, aa=False):
    """Extract `ref` from the zpack repo with git archive; never touches its checkout."""
    sha = resolve(cfg, ref)
    name = sha[:12] + ('_aa' if aa else '')
    dest = os.path.join(cfg['work'], 'trees', name)
    if not os.path.isdir(dest):
        tmp = dest + '.tmp'
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp)
        archive = subprocess.Popen(['git', '-C', cfg['zpack_repo'], 'archive', sha], stdout=subprocess.PIPE)
        subprocess.run(['tar', '-x', '-C', tmp], stdin=archive.stdout, check=True)
        if archive.wait():
            raise SystemExit(f'git archive {ref} failed')
        os.rename(tmp, dest)
    return dest


def label(cfg, ref):
    return ref if len(ref) <= 12 else resolve(cfg, ref)[:12]
