# Design

zpack-bench answers, for two zpack.nvim refs: did any plugin flip between lazy and eager or change structurally, and is startup with many plugins still faster than lazy.nvim, with paired statistics trustworthy enough to act on.

It replaces the ad-hoc harnesses used through zpack PRs #50-#54: `zpack-startup-perf/bench`, `zpack-lazyvim-compare`, `module-sole-claimant/real2` and the PR #54 review loop's per-round drivers.

## Layers
Each layer runs alone. All three share one config of paths and one way to build trees.

1. **`zb diff`**, functional differential.
   - Inputs: LazyVim all extras, N seeded subsets of the extras, and the live config.
   - Each runs through every zpack ref with `run_zpack.lua`, which does import and `resolve_all` only and installs nothing. lazy.nvim's own resolver is optional as an oracle.
   - Reports `lazy=` flips first, then P/E/W structure, then opts, then ERROR/CONFLICT.
2. **`zb probe`**, real-config probe.
   - Real startup of a config, with XDG config, data, state and cache isolated in APFS clones. Runs with and without a file argument.
   - Dumps plugin status, rtp, package.loaded, `g:` variables, autocmds, commands, messages, keymaps for every mode, and `colors_name`.
3. **`zb perf`**, cross-process startup.
   - Uses generated synthetic plugin sets at 150 and 300 plugins.
   - Shuffled paired rounds, with an A/A tree and the load recorded per row. Reports d-cpu medians with a 95% bootstrap CI.
   - Also provides `zb sprof` (jit.profile aggregate) and `zb inproc` (in-process import+resolve timer).

## Rules baked in
They were learned the hard way.

**Statistics**
- Compare paired d-cpu only, in shuffled order, with an A/A row. Absolute numbers move ~2x with load.
- Wait until the 1-minute load is 4 or below before each row, and flag rows that end above it.
- µs deltas are noise. ms-scale and super-linear growth matter. Lazy↔eager flips matter most.

**Isolation**
- Anything that runs zpack's import gets isolated XDG dirs, because the import can call the real `vim.pack.add`. In-process probes stub `vim.pack.add`.
- macOS `tempname()` is under the `/var` symlink, so temp roots are realpath'd.
- Kill only processes we started, by PID.
- Never touch the zpack checkout: trees come from `git -C <zpack_repo> archive <sha>`.

**Environment**
- Run nvim nightly and v0.12.0.
- Big generated roots live in `*.noindex` dirs, which Spotlight skips, and are gitignored.
- Generators are deterministic from a seed.

## Perf scenarios
A row is `<scenario><n>[@mode]`, with n ∈ {150, 300}. The 18-row matrix is the 9 scenarios below at both sizes. `miss` and the `@` modes are extras.

### Base set (`gen.py`)
This is the 2026-10-30 `gen.py`, ported with the same RNG call order, so seed 1 reproduces the old stores and configs.

**Kinds**
- One spec per plugin. Kinds are dealt from the 150-cycle `eager×30, event×30, verylazy×10, cmd×25, ft×15, keys×20, dep×20`, then shuffled.
- At 150 that is 30 eager, 40 event (`verylazy` counted as event), 25 cmd, 15 ft, 20 keys and 20 dep.

**Plugin contents**
- A `lua/<mod>/init.lua` that requires up to 3 submodules, plus 2-12 submodules of 40-400 lines.
- `plugin/` with probability .5, `after/plugin/` .1, `ftdetect/` .1, `ftplugin/` .1.
- Each plugin is a git repo with a lockfile entry, served from `https://example.invalid/bench/<name>`.

**Specs**
- `dep` plugins are `lazy = true`.
- Every non-dep plugin has a 30% chance of `dependencies` on 1-3 dep plugins.
- Specs are split 8 per file over `lua/plugins/groupNN.lua`.

### Scenarios
`NNN` is the plugin index, zero-padded to 3 digits.

**`realistic`**: the base config, run with no file argument.

**`file`**: `realistic` with a `.rs` file as the startup argument.

**`eager`**: every spec forced to `lazy = false`, including dep plugins.

**`cs`**: the `eager` config, except that bench000's spec becomes `lazy = false, priority = 1000, config = function() vim.cmd.colorscheme('bench000') end`.
- bench000 also ships this `colors/bench000.lua`:
  ```lua
  vim.cmd('hi clear')
  vim.g.colors_name = 'bench000'
  vim.api.nvim_set_hl(0, 'Normal', { fg = '#c0c0c0', bg = '#101010' })
  ```
- Recovered from r24-perf `sand/b150cs.noindex`: 149 of 150 specs equal `eager`.

**`inits`**: `realistic`, plus this `init` on every plugin with `idx % 3 == 0`, of any kind:
```lua
init = function() vim.g.bench_init_NNN = 1; pcall(require, 'bench_missing_NNN_a'); pcall(require, 'bench_missing_NNN_b') end
```
- The `init` is inserted right after `name`.
- That is 50 plugins at 150. `inits10` is the first 10 of them, idx < 30. It is used only for profiling and is not in the matrix.
- Recovered from r8-perf `config/inits` and `config/inits10`.

**`trig`**: `realistic`, with the cmd, keys and ft plugins at even indices switched to function-form triggers that still return the same values. That is 28 at 150.
- keys:
  ```lua
  keys = function(_, keys) require('benchNNN'); return { { '<leader>bNNN', function() end, desc = 'bN' } } end
  ```
  It requires the plugin's own module.
- cmd:
  ```lua
  cmd = function() pcall(require, 'bench_missing_cNNN'); return { 'BenchLazyNNN' } end
  ```
- ft:
  ```lua
  ft = function() pcall(require, 'benchEEE'); return { '<same ft>' } end
  ```
  `benchEEE` is an eager plugin's module.
- Which eager module each ft function picks was RNG output that can't be recovered. It is now drawn with `Random('<seed>:trig')` from the eager plugins, so the cost has the same shape but the targets may differ from PR #54's.
- Recovered from r8-perf `config/trig`.

**`trig10`**: `trig` restricted to the first 4 keys, first 3 cmd and first 3 ft plugins of the `trig` set. That is indices 12, 14, 36, 80 / 18, 24, 30 / 32, 34, 60 at 150. The other 18 keep their table form.
- Recovered from r8-perf `config/trig10`. Taking the first 10 by index does not reproduce it.

**`ftd`**: `realistic` on its own store, `store-ftd`.
- Every `ft` plugin, plus the first event, verylazy, cmd and keys plugins in index order up to 40 in total, become `ft = { 'ftdNNN' }, opts = {}`. Any `dependencies` stay. At 150 that is ft 15, event 11, cmd 9, keys 5. At 300 it is ft 30 plus 10 others.
- Each of those 40 gets `ftplugin/ftdNNN.vim` containing `let b:ftdNNN = 1`, and one ftdetect file, alternating by position:
  - even position, `ftdetect/ftdNNN.vim`: `au BufRead,BufNewFile *.ftdNNN set filetype=ftdNNN`
  - odd position, `ftdetect/ftdNNN.lua`: `vim.filetype.add({ extension = { ftdNNN = 'ftdNNN' } })`
- Each plugin's base `ftdetect/` file stays alongside the new one.
- With the base set's 10% ftdetect dirs, that is 50 ftdetect dirs and 47 ftplugin dirs at 150. At 300 it is about 70; PR #54 had 74.
- Recovered from r24-perf `sand/b150ftd.noindex`. 110 of 150 specs equal `realistic`; the changed ones start at indices 0, 1, 2, 5, 9, 10, 11, 12, 14, …, and bench000/001/002 have `ftd000.vim`, `ftd001.lua`, `ftd002.vim`.
- Two details are inferred from three files, not checked across all 40: whether `.vim` vs `.lua` alternates by position in the set or by index parity, and the file names.

**`fton`**: `ftd`, with `vim.cmd('filetype plugin indent on')` prepended to init.lua before the manager's setup. This applies to zpack and lazy.nvim alike, as PR #54's `PRE=` did.

**`miss`** (extra): the first `2n/3` plugins in index order are `lazy = false`, with this `config`:
```lua
config = function() for k = 1, 3 do pcall(require, 'bench_miss_NNN_' .. k) end end
```
- The rest keep their `realistic` spec. That is 100 eager and 50 lazy at 150.
- Rebuilt from TASK.md's description only: PR #54's `gen_miss.py` did not survive.

**`@vimenter`** (zpack targets only): `setup()` runs inside a `VimEnter` autocmd.

**`@plugin`** (zpack targets only): init.lua is empty, and `setup()` runs from the config's `plugin/zpack.lua`, where `v:vim_did_init` is 1.
- lazy.nvim has no equivalent of these modes, so they compare zpack refs only.

## Last known results (PR #54, from r24-perf)
- Setup: zpack 0a9e71f (`head`) and an A/A copy (`head_aa`) vs 241c9ba (`base`) vs lazy.nvim.
- 100 shuffled rounds per row, `SEED=24`, nvim nightly, 2026-11-05.
- Cells are d-cpu `head − X` in ms, with a 95% CI. `head cpu` is the absolute median.

| row | load | A/A | vs 241c9ba | vs lazy.nvim | head cpu |
|---|---|---|---|---|---|
| realistic150 | 2.5-2.5 | +0.48 [-0.09, +0.73] | +0.13 [-0.14, +0.43] | -2.47 [-2.84, -1.98] | 47.33 |
| file150 | 2.4-2.4 | +0.39 [-0.12, +0.87] | -0.16 [-0.43, +0.20] | -4.86 [-5.65, -4.47] | 66.17 |
| eager150 | 2.4-2.2 | +0.36 [-0.48, +0.78] | +0.82 [+0.17, +1.41] | -62.14 [-63.24, -61.24] | 81.63 |
| cs150 | 2.1-2.3 | +0.53 [-0.07, +0.99] | +0.51 [-0.44, +0.99] | -61.06 [-62.68, -60.00] | 79.99 |
| inits150 | 2.3-2.1 | -0.03 [-0.58, +0.69] | +0.68 [+0.38, +0.87] | -4.17 [-4.69, -3.84] | 58.64 |
| trig150 | 2.5-2.3 | +0.12 [-0.18, +0.53] | +2.03 [+1.66, +2.55] | -1.62 [-2.00, -1.17] | 59.93 |
| trig10_150 | 2.4-2.3 | -0.04 [-0.42, +0.33] | +1.26 [+0.91, +1.53] | -2.51 [-3.01, -1.87] | 52.76 |
| ftd150 | 2.9-2.5 | -0.04 [-0.30, +0.33] | +0.52 [+0.27, +0.73] | -1.63 [-2.11, -1.23] | 49.31 |
| fton150 | 3.9-3.6 | -0.18 [-0.35, -0.00] | +0.87 [+0.31, +1.26] | -0.78 [-1.27, -0.63] | 49.28 |
| realistic300 | 3.2-2.6 | -0.16 [-0.61, +0.19] | -0.12 [-0.60, +0.27] | -20.27 [-20.60, -19.63] | 79.09 |
| file300 | 2.6-2.4 | +0.32 [-0.07, +1.02] | -1.00 [-1.81, -0.67] | -34.75 [-35.55, -33.89] | 119.50 |
| eager300 | 2.5-1.7 | +0.03 [-0.90, +0.72] | -0.12 [-0.98, +0.88] | -263.90 [-265.32, -261.19] | 153.09 |
| cs300 | 3.6-2.5 | -0.05 [-0.93, +0.74] | +1.38 [+0.74, +2.06] | -262.01 [-263.68, -260.05] | 154.23 |
| inits300 | 1.8-2.4 | -0.36 [-0.89, +0.45] | +3.76 [+2.92, +4.23] | -24.19 [-24.87, -23.31] | 114.27 |
| trig300 | 2.5-2.2 | -0.48 [-1.16, +0.45] | +3.84 [+3.10, +4.60] | -26.01 [-26.98, -24.98] | 109.22 |
| trig10_300 | 2.6-2.3 | -0.51 [-0.83, +0.31] | +0.81 [+0.20, +1.37] | -21.76 [-22.73, -21.05] | 88.39 |
| ftd300 | 2.7-2.3 | +0.14 [-0.31, +0.59] | +0.29 [-0.25, +0.60] | -19.18 [-19.64, -18.43] | 86.10 |
| fton300 | 3.6-2.7 | -0.20 [-0.55, +0.46] | +3.74 [+3.03, +4.10] | -16.38 [-17.30, -15.69] | 86.42 |

PR #54's `all.sh` ran 9 scenarios per size: cs, realistic, file, eager, inits, trig, trig10, ftd and fton. That is 18 rows in all, and this repo's matrix is the same.

## Ported vs rewritten
- **Ported as-is:** `lvspecs.lua`, `run_zpack.lua` (it keeps its shims for older refs), `run_lazy.lua`, `userspecs.lua`, `sprof_init.lua`, and `perf.lua` as `inproc.lua`. `bughunt/` is copied unchanged into `extra/` and is not part of the CLI.
- **Rewritten:**
  - `gen.py` plus the scenario transforms are rewritten as `zbench/gen.py`.
  - `bench.py`, `shuf.py`, `run.sh`, `summ.sh` and `all.sh` are rewritten as `zbench/perf.py`.
  - `compare.sh` and `cmp.sh` are rewritten as `zbench/diff.py`.
  - `real2.py` and `real2k.py` are rewritten as `zbench/probe.py` and `lua/probe.lua`.
- **Dropped:**
  - `prof_init.lua` and `pair.py` hand laps, which sprof supersedes.
  - `ab.py`, `real.py`, `st*`, `micro*`, `jitprof.lua`, `rtpcheck.sh`, `perf_cold.*`, `count.lua`.
  - `shuf.py`'s OPEN in-process `:edit` timer.

## Decisions and dead ends
- Python 3.9 stdlib only, because the machine's python3 has no `tomllib`. Paths go in `config.json`, overridden by `local.json` (gitignored) and `ZB_*` env vars.
- The design and log live here, not in the workspace task folder. The workspace session guard blocks a background session from writing there.
- Gen check against the salvaged r8-perf output (`ref/salvage/r8-perf/b150.noindex`, 150 plugins, seed 1):
  - `realistic`, `eager`, `inits` and `inits10` configs are byte-identical.
  - `trig` and `trig10` are identical except the 9 and 3 ft-function targets.
  - The store is identical except the new `colors/bench000.lua`, which nothing sources at startup.
  - `ftd` matches every number recorded from r24 (see above).
  - `cs` matches the recorded bench000 spec line.
  - Git commit dates are now fixed, so lockfile revs are reproducible.
