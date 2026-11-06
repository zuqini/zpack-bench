# zpack-bench

zpack-bench validates zpack.nvim startup with many plugins and benchmarks it against lazy.nvim. For any two zpack refs it answers:
- Did any plugin flip between lazy and eager, or otherwise change structurally?
- Does a real config still start in the same state?
- Is startup still faster than lazy.nvim, by paired statistics you can act on?

It needs Python 3.9+ (stdlib only), nvim nightly and/or 0.12, a zpack.nvim clone and a lazy.nvim checkout. It runs on macOS: sandboxes are APFS clones (`cp -c`).

## The one command

```sh
./zb check <base-ref> <ref>
```

It runs `diff` and `probe` (3 reps) on nvim nightly and on 0.12, then `perf` on `realistic150,file150,inits150,trig150` with 60 rounds on both. Read each layer's VERDICT line first, then the final `CHECK:` line. It exits 1 if any of these hold:
- `diff` finds flips, structural or opts changes, new errors, or an output it couldn't compare.
- `probe` finds a state difference, a missing dump, or stderr the base doesn't have.
- `perf` flags a row: ERRORS, SANITY, LOAD, or not faster than lazy.nvim.

It takes roughly 10-15 minutes on an otherwise idle machine. Before the first `diff` or `check`, run `./zb fetch-lazyvim` once (see Setup).

## Layers

```sh
./zb diff 241c9ba bfd84e3 --seeds 40 --oracle      # functional differential
./zb probe 241c9ba bfd84e3 --reps 5                # real-config probe
./zb perf bfd84e3 --base 241c9ba --rows matrix --rounds 100 --nvim nightly,0.12
./zb perf bfd84e3 --rows realistic150@vimenter,realistic150@plugin
./zb sprof bfd84e3 inits300 --runs 30              # jit.profile of that row's startup, ms per startup
./zb inproc 241c9ba bfd84e3 --input all            # in-process import + resolve_all
./zb selftest                                       # determinism + every scenario starts + A/A diff
```

### `diff`
Runs LazyVim's specs and your live config through each ref's import and `resolve_all`, without installing anything:
- LazyVim with all extras, plus N subsets where each extra is kept with p=0.3.
- Your live config via `{ import = 'plugins' }`, with XDG isolated.

It reports, in order:
1. `lazy=` flips.
2. Structural lines that differ: P (plugins), E (dependency edges) and W (warnings).
3. Opts changes, with order-only list changes counted separately.
4. Errors that are new against the base.

What fails the verdict:
- Any output that errored or has no plugins, even when the base failed the same way.
- Flips, including a plugin present on one side only.
- Structural changes, opts changes that are more than list order, and new errors.

`--oracle` also runs lazy.nvim's own resolver on all extras and the subsets, and compares both the base and the ref against it. A dependency with no triggers of its own takes its parent's laziness, as zpack labels it. Disagreements the base already has are marked `(known)`. The oracle fails the verdict only on new ones or on oracle errors.

On LazyVim 301a3f7 the known set is 9 plugins whose only trigger is LazyVim's `LazyFile` event. lazy.nvim counts them lazy; zpack has resolved them eager since #51. See "zpack parity leads" in DESIGN.md.

Ignore `<expr>` lines: LazyVim is parsed with Tree-sitter, never executed, and any expression that isn't a literal becomes `"<expr>"`. `fetch-lazyvim` needs an authenticated `gh`.

### `probe`
Starts your real config (`user_config`) with a clone of `user_data` and XDG isolated. Each ref's tree goes first on `runtimepath`. It dumps the following, with and without a file argument:
- plugin status, rtp, `package.loaded`
- `g:` variables, autocmds, commands
- keymaps for every mode, including buffer-local ones
- the buffer's filetype and `colors_name`
- messages

For each section it reports whether trees differ. "varies between reps" means the section isn't stable even within one tree; dependency load order is one source. A difference in such a section may be noise, so compare the rep files in `work.noindex/probe/out/`.

What fails the verdict:
- A section that differs from the base.
- A missing dump.
- stderr that the base doesn't have.

New `zpack.*` modules are listed separately and don't fail the verdict.

Every plugin the config adds must already be installed in `user_data`. Otherwise vim.pack clones it from the network inside the sandbox, and the probe measures that instead.

### `perf`
Each target starts in its own process, in shuffled order each round, after 5 warmups. Cells are the d-cpu median of `ref − X` with a 95% bootstrap CI.

Targets:
- the A/A tree, a second copy of the first ref
- `--base`
- lazy.nvim
- with `--targets`, optionally `bare` (no plugins) and `native` (plain `vim.pack.add`, no setups)

Each target's line also shows `setups=N colors=X` from one extra startup.

A row is flagged when:
- **ERRORS:** any startup wrote to stderr or exited non-zero.
- **SANITY:** a zpack or lazy.nvim target's setups or colors differ from the first ref's. That catches a scenario that silently stopped loading plugins.
- **LOAD>4:** the machine was busy. Rerun the row.
- **NOT-FASTER-THAN-LAZY:** the CI of `ref − lazy` reaches 0 or above.

The run ends with a `VERDICT:` line and exits 1 if any row is flagged. Rows where the ref is slower than `--base` by more than the A/A's upper bound + 1 ms are listed, but don't fail. Raw samples go to `work.noindex/out/perf-*.json`.

Rough time: `--rows matrix --rounds 100` took 16 minutes on nightly, about 50 s per row with 4 targets.

Rows are `<scenario><n>[@vimenter|@plugin]`. A scenario whose name ends in a digit takes an underscore (`trig10_150`). `--rows` also accepts:
- `default`: the 4 rows `check` uses.
- `matrix`: 9 scenarios × {150, 300}, the 18 rows used through PR #54.
- `all`: `matrix` plus `miss` and the setup modes.

| scenario | what it is |
|---|---|
| `realistic` | 30 eager, the rest lazy on event/cmd/ft/keys or as dependencies, 8 specs per file |
| `file` | `realistic`, opening a `.rs` file |
| `eager` | every plugin eager |
| `cs` | `eager`, with a priority-1000 plugin calling `:colorscheme` in its `config` |
| `inits` | an `init` on every 3rd plugin, each probing 2 missing modules (`inits10`: the first 10) |
| `trig` | function-form cmd/keys/ft triggers that `require` modules (`trig10`: 4 keys, 3 cmd, 3 ft) |
| `ftd` | 40 `ft` plugins with `ftdetect/` and `ftplugin/` dirs |
| `fton` | `ftd` with `filetype plugin indent on` before setup |
| `miss` | 2/3 of plugins eager, each `config` probing 3 missing modules |
| `@vimenter`, `@plugin` | zpack's `setup()` in a VimEnter autocmd, or from the config's `plugin/` (zpack targets only) |

The exact rules are in DESIGN.md.

## Reading perf numbers
- Compare paired d-cpu only. Absolute times move about 2x with machine load.
- Trust a delta only when it is clearly outside the A/A row's CI.
- `perf` waits for the 1-minute load to fall to `max_load` (4) before each row and flags rows that end above it.
- Microsecond deltas are noise. ms-scale costs, growth from 150 to 300 plugins, and lazy↔eager flips are what matter.

## Setup
- `config.json` holds the paths (nvim binaries, lazy.nvim, the zpack repo, the live config and its data dir). Override them in `local.json` (gitignored) or with `ZB_LAZY`, `ZB_ZPACK_REPO`, `ZB_USER_CONFIG`, `ZB_USER_DATA` or `ZB_WORK`.
- `./zb fetch-lazyvim [sha]` downloads LazyVim's source as data, through an authenticated `gh`. The acceptance runs used 301a3f71007c.
- `selftest` defaults to `--ref origin/HEAD`, which must be set in the zpack clone (`git remote set-head origin -a`).
- zpack trees come from `git archive <sha>` into `work.noindex/trees/`. Your zpack checkout is never touched.
- Generated plugin sets go in `work.noindex/sets/n<n>-s<seed>-g<hash of gen.py>/`. They are deterministic from (n, seed), git commit dates included, so editing the generator makes a new set rather than reusing a stale one.

## Rules baked in
- Anything that runs zpack's import uses isolated XDG dirs, because the import may call the real `vim.pack.add`. In-process scripts stub it.
- Temp roots are realpath'd: macOS `tempname()` sits under the `/var` symlink, which changes how `:packadd!` matches rtp entries.
- Each child process has a timeout. Only that child is killed, by PID.
- Generated roots live in `*.noindex` dirs, which Spotlight skips.

## extra/bughunt
These are the edge-shape fuzzers from zpack PR #49, copied unchanged. They are not part of the CLI.

```sh
SCEN=extra/bughunt/scen/s1.lua extra/bughunt/run.sh <ref> probe_test.lua
GEN=extra/bughunt/gen.lua FIRST=1 N=300 MODE=plain NPERM=6 extra/bughunt/run.sh <ref> orderfuzz_test.lua
GEN=extra/bughunt/gen.lua SEED=<n> MODE=plain extra/bughunt/run.sh <ref> minimize_test.lua
LAZY=~/.local/share/nvim/lazy/lazy.nvim nvim -u NONE -l extra/bughunt/lazyrun.lua extra/bughunt/scen/s1.lua
```

`run.sh` copies the tree plus the tests, links a LuaRocks tree that has busted (`ROCKS`, default `<zpack_repo>/.luarocks`), and runs busted with the configured nightly nvim and XDG isolated.

Expect a few `DEP` seeds: cycles where plugins' specs disable each other have no order-free answer. Against current zpack (checked at bfd84e3), `probe_harness`'s stale-state check prints `CHECK ERR ... sort_specs`, because that internal was removed. The probe output is still valid.
