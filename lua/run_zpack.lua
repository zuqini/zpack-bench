-- nvim -u NONE -l run_zpack.lua <zpack_tree> <lv_root> <mode> [seed] [with_opts]
local tree, lv_root, mode, seed, with_opts = _G.arg[1], _G.arg[2], _G.arg[3], tonumber(_G.arg[4] or '0'), _G.arg[5] == '1'
package.path = tree .. '/lua/?.lua;' .. tree .. '/lua/?/init.lua;' .. package.path
local here = debug.getinfo(1, 'S').source:sub(2):match('(.*/)')
local list, failed
if mode == 'file' then
  list, failed = dofile(lv_root), {}
elseif mode == 'user' then
  list, failed = dofile(here .. 'userspecs.lua')(lv_root)
else
  list, failed = dofile(here .. 'lvspecs.lua')(lv_root, mode, seed)
end

local utils = require('zpack.utils')
local notes = {}
utils.schedule_notify = function(msg, level)
  notes[#notes + 1] = { msg = msg, level = level }
end
local state = require('zpack.state')
state.config = { defaults = {} }
local ctx = { src_with_init = {}, registered_startup_packs = {}, registered_lazy_packs = {}, confirm = false, defaults = {}, _imported_functions = {}, early_plugins = {}, import_paths = {}, missing_owners = {}, settled_owners = {}, import_notes = {}, validated_specs = {}, enabled_results = {}, cond_results = {} }
-- Nothing here may install: an import can add its plugin early.
vim.pack.add = function() end

local calls = {}
local function wrap(fn)
  return function(...)
    calls[fn] = (calls[fn] or 0) + 1
    return fn(...)
  end
end
-- count function-form enabled calls
local function count_enabled(spec, seen)
  if type(spec) ~= 'table' or seen[spec] then return end
  seen[spec] = true
  if type(spec.enabled) == 'function' then
    local f = spec.enabled
    spec.enabled = function(...)
      calls[f] = (calls[f] or 0) + 1
      return f(...)
    end
  end
  for k, v in pairs(spec) do
    if type(k) == 'number' or k == 'dependencies' or k == 'specs' then
      count_enabled(v, seen)
    end
  end
end
count_enabled(list, {})

local import_module = require('zpack.import')
-- Refs from zpack.import_run on keep the pass loop there.
local has_import_run, import_run = pcall(require, 'zpack.import_run')
local import_all = import_module.import_all or (has_import_run and import_run.import_all)
-- Refs that expose new_graph build the graph by hand; later ones only through import_all.
local exposes_graph = import_module.new_graph ~= nil
if exposes_graph then
  ctx.graph = import_module.new_graph(ctx)
end
local imported
local t0 = vim.uv.hrtime()
if exposes_graph or not import_all then
  for _, m in ipairs(list) do
    import_module.import_specs(m, ctx)
  end
  if import_module.flush_notes then
    import_module.flush_notes(ctx)
  end
else
  -- Refs with zpack.ImportRun return their state and read confirm from the table; earlier ones fill ctx.
  imported = import_all(list, ctx)
end
imported = imported or ctx
local t1 = vim.uv.hrtime()
-- enabled_results: refs that keep it off the graph take it as an argument.
local ok, packs = pcall(require('zpack.merge').resolve_all, imported.graph, imported.enabled_results)
local t2 = vim.uv.hrtime()
local out = {}
local function p(s) out[#out + 1] = s end
if not ok then
  p('ERROR resolve_all: ' .. tostring(packs))
  packs = {}
end

-- The pre-seed moved to register_all: compute what it would.
if ok then
  local computed = false
  for src, e in pairs(state.spec_registry) do
    if e.is_lazy_resolved == nil then
      -- Refs that keep the graph private take the entry; earlier ones its merged spec.
      local lazy_arg = (exposes_graph or not import_all) and e.merged_spec or e
      e.is_lazy_resolved = require('zpack.lazy').is_lazy(lazy_arg, nil, src)
      computed = true
    end
  end
  if computed then state.lazy_parent_cache = {} end
end

local GH = 'https://github.com/'
local function short(s) return (tostring(s):gsub('^' .. vim.pesc(GH), '')) end

local names = {}
for _, ps in ipairs(packs) do
  local e = state.spec_registry[ps.src]
  local name = ps.name
  if names[name] then p('CONFLICT name ' .. name .. ' ' .. short(names[name]) .. ' vs ' .. short(ps.src)) end
  names[name] = ps.src
  p(('P %s src=%s ver=%s lazy=%s'):format(name, short(ps.src), tostring(ps.version), tostring(e.is_lazy_resolved)))
end
for src, deps in pairs(state.dependency_graph) do
  for d in pairs(deps) do
    if src ~= d then
      p(('E %s -> %s'):format(short(src), short(d)))
    end
  end
end
local ncalls = 0
for _, n in pairs(calls) do ncalls = ncalls + n end
p('ENABLED_CALLS total=' .. ncalls)
for _, n in ipairs(notes) do
  if n.level and n.level >= vim.log.levels.WARN then
    p('W ' .. n.msg:gsub('\n', ' '))
  elseif n.level == vim.log.levels.DEBUG then
    p('D ' .. n.msg:gsub('\n', ' '))
  end
end
for _, f in ipairs(failed) do p('MODFAIL ' .. f) end

local function ser(v, depth, seen)
  depth = depth or 0
  seen = seen or {}
  local t = type(v)
  if t == 'function' then return '<fn>' end
  if t == 'userdata' then return v == vim.NIL and 'NIL' or '<ud>' end
  if t ~= 'table' then return t == 'string' and ('%q'):format(v) or tostring(v) end
  if seen[v] or depth > 8 then return '<cycle>' end
  seen[v] = true
  local keys = vim.tbl_keys(v)
  table.sort(keys, function(a, b)
    if type(a) == type(b) and (type(a) == 'number' or type(a) == 'string') then return a < b end
    return type(a) < type(b)
  end)
  local parts = {}
  for _, k in ipairs(keys) do
    parts[#parts + 1] = (type(k) == 'number' and '' or (tostring(k) .. '=')) .. ser(v[k], depth + 1, seen)
  end
  seen[v] = nil
  return '{' .. table.concat(parts, ',') .. '}'
end

if with_opts then
  local merge = require('zpack.merge')
  for _, ps in ipairs(packs) do
    local e = state.spec_registry[ps.src]
    if e.has_opts then
      local plugin = { spec = e.merged_spec, name = ps.name, path = '/x/' .. ps.name, dir = '/x/' .. ps.name, dependencies = {} }
      local okk, res = pcall(merge.resolve_opts or require('zpack.opts').resolve_opts, e.sorted_specs, plugin, e.merged_spec.opts_extend)
      p(('O %s %s'):format(ps.name, okk and ser(res) or ('ERR ' .. tostring(res):sub(1, 100))))
    end
  end
end

table.sort(out)
io.write(table.concat(out, '\n'), '\n')
io.stderr:write(('TIMING import=%.0fus resolve=%.0fus specs=%d\n'):format((t1 - t0) / 1e3, (t2 - t1) / 1e3, (imported.graph and imported.graph.next_import_order) or state.import_order or -1))
