-- nvim -u NONE -l perf.lua <trees_dir> <input_root> <mode> <rounds> <tree> [<tree>...]
-- Times import + resolve_all per tree in ONE process, rotating the tree order each round.
local trees_dir, root, mode, rounds = _G.arg[1], _G.arg[2], _G.arg[3], tonumber(_G.arg[4] or '20')
local here = debug.getinfo(1, 'S').source:sub(2):match('(.*/)')
local build_lv = dofile(here .. 'lvspecs.lua')
local build_user = dofile(here .. 'userspecs.lua')
local base_path = package.path
local TREES = {}
for i = 5, #_G.arg do TREES[#TREES + 1] = _G.arg[i] end

local function fresh_list()
  if mode == 'user' then
    for k in pairs(package.loaded) do
      if k:match('^plugins%.') then package.loaded[k] = nil end
    end
    return (build_user(root))
  end
  return (build_lv(root, mode, 0))
end

local function run(tree)
  for k in pairs(package.loaded) do
    if k:match('^zpack') then package.loaded[k] = nil end
  end
  package.path = trees_dir .. '/' .. tree .. '/lua/?.lua;' .. trees_dir .. '/' .. tree .. '/lua/?/init.lua;' .. base_path
  local list = fresh_list()
  local utils = require('zpack.utils')
  utils.schedule_notify = function() end
  local state = require('zpack.state')
  state.config = { defaults = {} }
  vim.pack.add = function() end
  local import = require('zpack.import')
  -- Refs from zpack.import_run on keep the pass loop there.
  local has_import_run, import_run = pcall(require, 'zpack.import_run')
  local import_all = import.import_all or (has_import_run and import_run.import_all)
  local merge = require('zpack.merge')
  local ctx = { src_with_init = {}, registered_startup_packs = {}, registered_lazy_packs = {}, confirm = false, defaults = {}, _imported_functions = {}, early_plugins = {}, import_paths = {}, missing_owners = {}, settled_owners = {}, import_notes = {}, validated_specs = {}, enabled_results = {} }
  -- Refs that expose new_graph build the graph by hand; later ones only through import_all.
  local exposes_graph = import.new_graph ~= nil
  if exposes_graph then ctx.graph = import.new_graph(ctx) end
  collectgarbage('collect')
  local imported
  local t0 = vim.uv.hrtime()
  if exposes_graph or not import_all then
    for _, m in ipairs(list) do import.import_specs(m, ctx) end
  else
    -- Refs with zpack.ImportRun return their state; earlier ones fill ctx.
    imported = import_all(list, ctx)
  end
  imported = imported or ctx
  local t1 = vim.uv.hrtime()
  merge.resolve_all(imported.graph, imported.enabled_results)
  local t2 = vim.uv.hrtime()
  return (t1 - t0) / 1e3, (t2 - t1) / 1e3
end

local res = {}
for _, t in ipairs(TREES) do res[t] = { imp = {}, res = {} } end
for _ = 1, 3 do for _, t in ipairs(TREES) do run(t) end end
for r = 1, rounds do
  for i = 0, #TREES - 1 do
    local t = TREES[(r + i) % #TREES + 1]
    local a, b = run(t)
    table.insert(res[t].imp, a)
    table.insert(res[t].res, b)
  end
end
local function median(xs)
  table.sort(xs)
  return xs[math.floor(#xs / 2) + 1]
end
for _, t in ipairs(TREES) do
  print(('%-6s import %7.0f us  resolve_all %7.0f us  total %7.0f us'):format(t, median(res[t].imp), median(res[t].res),
    median(res[t].imp) + median(res[t].res)))
end
