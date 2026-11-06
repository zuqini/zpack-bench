-- nvim -u NONE -l inproc.lua <trees_dir> <lv_root|spec_file> <all|subset|file> <rounds> <tree> [<tree>...]
-- Times import + resolve_all per tree in ONE process, rotating the tree order each round.
local trees_dir, root, mode, rounds = _G.arg[1], _G.arg[2], _G.arg[3], tonumber(_G.arg[4] or '20')
local here = debug.getinfo(1, 'S').source:sub(2):match('(.*/)')
local build_lv = dofile(here .. 'lvspecs.lua')
local shim = dofile(here .. 'zpack_shim.lua')
local base_path = package.path
local TREES = {}
for i = 5, #_G.arg do TREES[#TREES + 1] = _G.arg[i] end

local function fresh_list()
  if mode == 'file' then
    for k in pairs(package.loaded) do
      if k == 'plugins' or k:match('^plugins%.') then package.loaded[k] = nil end
    end
    return dofile(root)
  end
  return (build_lv(root, mode, 0))
end

local function run(tree)
  for k in pairs(package.loaded) do
    if k:match('^zpack') then package.loaded[k] = nil end
  end
  package.path = trees_dir .. '/' .. tree .. '/lua/?.lua;' .. trees_dir .. '/' .. tree .. '/lua/?/init.lua;' .. base_path
  local r = shim(fresh_list())
  return r.import_us, r.resolve_us
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
