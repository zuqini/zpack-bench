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
  if not ok then parts[#parts + 1] = 'ERR:' .. tostring(err):sub(1, 120) end
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
  for src, e in pairs(state.spec_registry) do
    lz[#lz + 1] = short(src) .. (e.is_lazy_resolved and ':L' or ':E')
  end
  table.sort(lz)
  parts[#parts + 1] = 'Z[' .. table.concat(lz, ',') .. ']'
  helpers.cleanup_test_env()
  return table.concat(parts, ' ')
end

describe('orderfuzz', function()
  it('runs', function()
    local first = tonumber(os.getenv('FIRST') or '1')
    local n = tonumber(os.getenv('N') or '200')
    local mode = os.getenv('MODE') or 'plain'
    local nperm = tonumber(os.getenv('NPERM') or '6')
    local out = {}
    for seed = first, first + n - 1 do
      local base = outcome(G.make(seed, nil, mode))
      local diff
      for p = 1, nperm do
        local o = outcome(G.make(seed, seed * 100 + p, mode))
        if o ~= base then diff = { p = p, o = o } break end
      end
      if diff then
        out[#out + 1] = ('SEED %d DEP perm=%d\n  base: %s\n  perm: %s'):format(seed, diff.p, base, diff.o)
      else
        out[#out + 1] = ('SEED %d OK %s'):format(seed, base)
      end
    end
    io.stdout:write(table.concat(out, '\n') .. '\n')
  end)
end)
