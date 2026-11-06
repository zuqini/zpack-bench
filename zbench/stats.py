import random
import statistics as st


def boot_median(d, seed=7, n=2000):
    """Median of d with a 95% bootstrap CI."""
    rng = random.Random(seed)
    b = sorted(st.median(rng.choices(d, k=len(d))) for _ in range(n))
    return st.median(d), b[int(0.025 * n)], b[int(0.975 * n)]


def paired(a, b, seed=7):
    return boot_median([x - y for x, y in zip(a, b)], seed)


def fmt(m, lo, hi):
    return f'{m:+7.2f} [{lo:+.2f}, {hi:+.2f}]'
