local helpers = require('helpers')
local H = {}
local GH = 'https://github.com/'
local function short(s) return (tostring(s):gsub('^' .. vim.pesc(GH), '')) end
H.short = short

-- Consistency check on surviving entries: merged_spec / sorted_specs / has_opts /
-- _is_dependency must match what the remaining specs and listings give.
function H.check_stale(state, merge, rec, out)
  local live = {}
  for src, e in pairs(state.spec_registry) do
    for _, s in ipairs(e.specs or {}) do live[s] = src end
  end
  for src, e in pairs(state.spec_registry) do
    local sorted = merge.sort_specs(e.specs)
    local same = #sorted == #(e.sorted_specs or {})
    for i = 1, #sorted do if sorted[i] ~= e.sorted_specs[i] then same = false end end
    if not same then out[#out + 1] = 'STALE sorted_specs: ' .. short(src) end
    local fresh = merge.merge_spec_array(sorted)
    for _, k in ipairs({ 'lazy', 'event', 'cmd', 'ft', 'keys', 'config', 'main', 'priority', 'version', 'branch', 'tag', 'opts_extend', 1, 'dependencies', 'dev', 'dir', 'url', 'src' }) do
      if not vim.deep_equal(fresh[k], e.merged_spec[k]) then
        out[#out + 1] = ('STALE merged_spec.%s on %s: %s vs fresh %s'):format(k, short(src), vim.inspect(e.merged_spec[k]), vim.inspect(fresh[k]))
      end
    end
    local hopts = false
    for _, s in ipairs(e.specs) do if s.opts ~= nil then hopts = true end end
    if hopts ~= (e.has_opts or false) then out[#out + 1] = 'STALE has_opts on ' .. short(src) end
    if rec then
      for _, s in ipairs(e.specs) do
        local exp
        if rec.top[s] then exp = false else
          exp = true
          local any = false
          for p in pairs(rec.parents[s] or {}) do
            if live[p] then
              any = true
              local in_specs = false
              if type(p.specs) == 'table' then
                for _, x in ipairs(p.specs[1] == nil and p.specs or (type(p.specs[1]) == 'table' and p.specs or { p.specs })) do if x == s then in_specs = true end end
                if p.specs == s then in_specs = true end
              end
              if not rec.children[p][s] or in_specs then exp = false end
            end
          end
          if not any then exp = '?no-live-parent' end
        end
        if exp ~= s._is_dependency then
          out[#out + 1] = ('STALE _is_dependency on a spec of %s ([1]=%s): %s, expected %s'):format(short(src), tostring(s[1]), tostring(s._is_dependency), tostring(exp))
        end
      end
    end
  end
end

function H.run(label, spec_fn, extra)
  helpers.setup_test_env()
  _G.ENABLED_CALLS = {}
  local orig_add = vim.pack.add
  local conflict = {}
  vim.pack.add = function(specs, opts)
    local by_name = {}
    for _, p in ipairs(specs) do
      local name = p.name or p.src:match('[^/]+$')
      if by_name[name] and by_name[name] ~= p.src then
        table.insert(conflict, name .. ': ' .. by_name[name] .. ' vs ' .. p.src)
      end
      by_name[name] = p.src
    end
    return orig_add(specs, opts)
  end
  local state = require('zpack.state')
  local merge = require('zpack.merge')
  local rec
  local orig_resolve = merge.resolve_all
  merge.resolve_all = function(...)
    if state.top_specs then
      rec = { top = state.top_specs, parents = state.spec_parents, children = state.spec_children }
    end
    return orig_resolve(...)
  end
  local spec = spec_fn()
  local ok, err = pcall(function()
    require('zpack').setup({ spec = spec, defaults = { confirm = false } })
    helpers.flush_pending()
    if extra then extra() end
  end)
  merge.resolve_all = orig_resolve
  local out = { '=== ' .. label }
  if not ok then out[#out + 1] = 'ERROR: ' .. tostring(err) end
  if #conflict > 0 then out[#out + 1] = 'CONFLICT: ' .. table.concat(conflict, '; ') end
  local packs = {}
  for _, call in ipairs(_G.test_state.vim_pack_calls) do
    for _, p in ipairs(call) do packs[#packs + 1] = p.name .. '<-' .. short(p.src) end
  end
  table.sort(packs)
  out[#out + 1] = 'packs: ' .. table.concat(packs, ', ')
  local edges = {}
  for s, deps in pairs(state.dependency_graph) do
    for d in pairs(deps) do edges[#edges + 1] = short(s) .. '->' .. short(d) end
  end
  table.sort(edges)
  out[#out + 1] = 'graph: ' .. table.concat(edges, ', ')
  local lazy = {}
  for src, e in pairs(state.spec_registry) do
    lazy[#lazy + 1] = short(src) .. (e.is_lazy_resolved and ':lazy' or ':eager')
  end
  table.sort(lazy)
  out[#out + 1] = 'lazy: ' .. table.concat(lazy, ' ')
  out[#out + 1] = 'loaded: ' .. table.concat(_G.test_state.loaded_plugins, ', ')
  if next(_G.ENABLED_CALLS) then
    local c = {}
    for k, v in pairs(_G.ENABLED_CALLS) do c[#c + 1] = k .. '=' .. v end
    table.sort(c)
    out[#out + 1] = 'enabled calls: ' .. table.concat(c, ' ')
  end
  for _, n in ipairs(_G.test_state.notifications) do
    if n.level and n.level >= vim.log.levels.DEBUG then
      out[#out + 1] = 'notify[' .. n.level .. ']: ' .. n.msg
    end
  end
  if ok then
    local ok2, e2 = pcall(H.check_stale, state, merge, rec, out)
    if not ok2 then out[#out + 1] = 'CHECK ERR: ' .. tostring(e2) end
  end
  if H.extra_out then
    local ok3, e3 = pcall(H.extra_out, state, out)
    if not ok3 then out[#out + 1] = 'EXTRA ERR: ' .. tostring(e3) end
  end
  print(table.concat(out, '\n'))
  vim.pack.add = orig_add
  helpers.cleanup_test_env()
  return state
end
return H
