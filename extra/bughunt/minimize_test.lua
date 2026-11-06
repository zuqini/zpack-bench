local helpers = require('helpers')
local G = dofile(os.getenv('GEN'))
local GH = 'https://github.com/'
local function short(s) return (tostring(s):gsub('^' .. vim.pesc(GH), '')) end

local function outcome(spec)
  helpers.setup_test_env()
  local ok, err = pcall(function()
    require('zpack').setup({ spec = spec, defaults = { confirm = false } })
    helpers.flush_pending()
  end)
  local state = require('zpack.state')
  local parts = {}
  if not ok then parts[#parts + 1] = 'ERR:' .. tostring(err):sub(1, 200) end
  local packs = {}
  for _, call in ipairs(_G.test_state.vim_pack_calls) do
    for _, p in ipairs(call) do packs[#packs + 1] = p.name .. '<-' .. short(p.src) end
  end
  table.sort(packs)
  parts[#parts + 1] = 'P[' .. table.concat(packs, ',') .. ']'
  local edges = {}
  for s, deps in pairs(state.dependency_graph) do
    for d in pairs(deps) do edges[#edges + 1] = short(s) .. '>' .. short(d) end
  end
  table.sort(edges)
  parts[#parts + 1] = 'G[' .. table.concat(edges, ',') .. ']'
  local lz = {}
  for src, e in pairs(state.spec_registry) do lz[#lz + 1] = short(src) .. (e.is_lazy_resolved and ':L' or ':E') end
  table.sort(lz)
  parts[#parts + 1] = 'Z[' .. table.concat(lz, ',') .. ']'
  helpers.cleanup_test_env()
  return table.concat(parts, ' ')
end

local function copy(t, memo)
  if type(t) ~= 'table' then return t end
  if memo[t] then return memo[t] end
  local c = {}
  memo[t] = c
  for k, v in pairs(t) do c[k] = copy(v, memo) end
  return c
end

local function perms(n)
  local res = {}
  local function rec(a, k)
    if k > n then res[#res + 1] = vim.list_slice(a) return end
    for i = k, n do a[k], a[i] = a[i], a[k]; rec(a, k + 1); a[k], a[i] = a[i], a[k] end
  end
  local a = {}
  for i = 1, n do a[i] = i end
  rec(a, 1)
  return res
end

local function order_dep(template)
  local n = #template
  local ps
  if n <= 5 then ps = perms(n) else
    ps = { (function() local a = {} for i = 1, n do a[i] = i end return a end)() }
    for k = 1, 30 do
      local r = G.rng(k * 7919 + 13)
      local a = {}
      for i = 1, n do a[i] = i end
      for i = n, 2, -1 do local j = r(i); a[i], a[j] = a[j], a[i] end
      ps[#ps + 1] = a
    end
  end
  local base
  for _, p in ipairs(ps) do
    local c = copy(template, {})
    local top = {}
    for i, j in ipairs(p) do top[i] = c[j] end
    local o = outcome(top)
    if not base then base = { o = o, p = p } elseif o ~= base.o then
      return true, base, { o = o, p = p }
    end
  end
  return false
end

-- enumerate edits on template (in place mutation, returns undo)
local function edits(template)
  local list = {}
  local seen = {}
  local function visit(t)
    if seen[t] then return end
    seen[t] = true
    for _, f in ipairs({ 'enabled', 'optional', 'event', 'name', 'url' }) do
      if t[f] ~= nil then
        list[#list + 1] = function() local v = t[f]; t[f] = nil; return function() t[f] = v end end
      end
    end
    for _, f in ipairs({ 'dependencies', 'specs' }) do
      local l = t[f]
      if type(l) == 'table' then
        for i = #l, 1, -1 do
          list[#list + 1] = function() local v = table.remove(l, i); return function() table.insert(l, i, v) end end
        end
        list[#list + 1] = function() t[f] = nil; return function() t[f] = l end end
        for _, v in ipairs(l) do if type(v) == 'table' then visit(v) end end
      end
    end
  end
  for i = #template, 1, -1 do
    list[#list + 1] = function() local v = table.remove(template, i); return function() table.insert(template, i, v) end end
  end
  for _, s in ipairs(template) do visit(s) end
  return list
end

local ids
local function show(t)
  if type(t) ~= 'table' then return vim.inspect(t) end
  if ids.map[t] then return '<T' .. ids.map[t] .. '>' end
  ids.n = ids.n + 1; ids.map[t] = ids.n
  local me = ids.n
  local parts = { vim.inspect(t[1]) }
  for _, f in ipairs({ 'name', 'url', 'enabled', 'optional', 'event' }) do
    if t[f] ~= nil then parts[#parts + 1] = f .. ' = ' .. vim.inspect(t[f]) end
  end
  for _, f in ipairs({ 'dependencies', 'specs' }) do
    if t[f] then
      local s = {}
      for _, v in ipairs(t[f]) do s[#s + 1] = show(v) end
      parts[#parts + 1] = f .. ' = { ' .. table.concat(s, ', ') .. ' }'
    end
  end
  return 'T' .. me .. '{ ' .. table.concat(parts, ', ') .. ' }'
end

describe('min', function()
  it('runs', function()
    local seed = tonumber(os.getenv('SEED'))
    local mode = os.getenv('MODE') or 'plain'
    local template = G.make(seed, nil, mode)
    assert(order_dep(template), 'not order dependent at start')
    local changed = true
    while changed do
      changed = false
      for _, e in ipairs(edits(template)) do
        local undo = e()
        if order_dep(template) then
          changed = true
          break
        else
          undo()
        end
      end
    end
    local _, a, b = order_dep(template)
    ids = { n = 0, map = {} }
    local lines = {}
    for _, s in ipairs(template) do lines[#lines + 1] = '  ' .. show(s) end
    io.stdout:write(('MIN seed %d:\n%s\n  order %s -> %s\n  order %s -> %s\n'):format(seed, table.concat(lines, '\n'),
      table.concat(a.p, ','), a.o, table.concat(b.p, ','), b.o))
  end)
end)
