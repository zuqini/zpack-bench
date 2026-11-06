#!/bin/sh
# usage: extra/bughunt/run.sh <zpack ref> <probe_test.lua|orderfuzz_test.lua|minimize_test.lua>
# env: SCEN=<scenario file> for probe_test; GEN=extra/bughunt/gen.lua FIRST N MODE NPERM / SEED for the fuzzers;
#      ROCKS=<a LuaRocks tree with busted> (default: <zpack_repo>/.luarocks from config.json)
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
ZB=$(cd "$HERE/../.." && pwd)
TREE=$(cd "$ZB" && python3 -c "import sys; from zbench import config, trees; print(trees.build(config.load(), sys.argv[1]))" "$1")
cfg() { (cd "$ZB" && python3 -c "import sys; from zbench import config; c = config.load(); print(eval(sys.argv[1]))" "$1"); }
W=$(cfg "c['work']")/bughunt/$(basename "$TREE")
NVIM=$(cfg "config.nvim(c, 'nightly')")
rm -rf "$W"; mkdir -p "$W/xdg"; cp -cR "$TREE/" "$W/tree"
cp "$HERE/harness.lua" "$W/tree/tests/probe_harness.lua"
cp "$HERE"/*_test.lua "$W/tree/tests/"
ln -s "${ROCKS:-$(cfg "c['zpack_repo']")/.luarocks}" "$W/tree/.luarocks"
for v in SCEN GEN; do eval "x=\${$v:-}"; [ -n "$x" ] && export $v="$(cd "$(dirname "$x")" && pwd)/$(basename "$x")"; done
cd "$W/tree"
XDG_CONFIG_HOME="$W/xdg/config" XDG_DATA_HOME="$W/xdg/data" XDG_STATE_HOME="$W/xdg/state" XDG_CACHE_HOME="$W/xdg/cache" \
  "$NVIM" -u NONE -l tests/busted.lua "tests/$2"
