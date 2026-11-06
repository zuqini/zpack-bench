-- import + resolve_all of a spec list with the zpack modules on package.path, across zpack versions.
-- Nothing installs: vim.pack.add is stubbed. Notifications are collected instead of shown.
return function(list)
  local notes = {}
  require('zpack.utils').schedule_notify = function(msg, level)
    notes[#notes + 1] = { msg = msg, level = level }
  end
  local state = require('zpack.state')
  state.config = { defaults = {} }
  vim.pack.add = function() end
  local ctx = { src_with_init = {}, registered_startup_packs = {}, registered_lazy_packs = {}, confirm = false,
    defaults = {}, _imported_functions = {}, early_plugins = {}, import_paths = {}, missing_owners = {},
    settled_owners = {}, import_notes = {}, validated_specs = {}, enabled_results = {}, cond_results = {} }
  local import = require('zpack.import')
  -- Refs from zpack.import_run on keep the pass loop there.
  local has_import_run, import_run = pcall(require, 'zpack.import_run')
  local import_all = import.import_all or (has_import_run and import_run.import_all)
  -- Refs that expose new_graph build the graph by hand; later ones only through import_all.
  local by_hand = import.new_graph ~= nil or not import_all
  if import.new_graph then ctx.graph = import.new_graph(ctx) end
  collectgarbage('collect')
  local t0 = vim.uv.hrtime()
  local imported
  if by_hand then
    for _, m in ipairs(list) do import.import_specs(m, ctx) end
    if import.flush_notes then import.flush_notes(ctx) end
  else
    -- Refs with zpack.ImportRun return their state; earlier ones fill ctx.
    imported = import_all(list, ctx)
  end
  imported = imported or ctx
  local t1 = vim.uv.hrtime()
  -- enabled_results: refs that keep it off the graph take it as an argument.
  local ok, packs = pcall(require('zpack.merge').resolve_all, imported.graph, imported.enabled_results)
  local t2 = vim.uv.hrtime()
  return { ok = ok, packs = packs, state = state, notes = notes, by_hand = by_hand, imported = imported,
    import_us = (t1 - t0) / 1e3, resolve_us = (t2 - t1) / 1e3 }
end
