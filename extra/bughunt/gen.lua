-- Deterministic random spec generator. G.make(seed, perm_seed, mode) returns a
-- fresh top-level spec list; perm_seed shuffles only the top-level order.
local G = {}
local function rng(seed)
  local s = seed % 2147483647
  if s <= 0 then s = s + 2147483646 end
  return function(n)
    s = (s * 16807) % 2147483647
    return (s % n) + 1
  end
end
G.rng = rng

function G.make(seed, perm_seed, mode)
  local r = rng(seed)
  local npl = 4 + r(3)
  local pool = {}
  for i = 1, npl do pool[i] = 'test/p' .. i end
  local made = {}
  local function new_spec(depth, as_dep)
    if #made > 0 and r(6) == 1 then
      return made[r(#made)]
    end
    local s = { pool[r(npl)] }
    if r(5) == 1 then s.enabled = false end
    if r(4) == 1 then s.optional = true end
    if r(4) == 1 then s.event = 'BufRead' end
    if mode == 'rich' then
      if r(10) == 1 then s.name = 'alias' .. r(2) end
      if r(10) == 1 then s.url = 'https://example.com/fork/' .. s[1]:match('[^/]+$') end
    end
    made[#made + 1] = s
    if depth < 3 then
      if r(3) == 1 then
        s.dependencies = {}
        for _ = 1, r(2) do
          if r(4) == 1 then
            s.dependencies[#s.dependencies + 1] = pool[r(npl)]
          else
            s.dependencies[#s.dependencies + 1] = new_spec(depth + 1, true)
          end
        end
      end
      if r(4) == 1 then
        s.specs = {}
        for _ = 1, r(2) do s.specs[#s.specs + 1] = new_spec(depth + 1, false) end
      end
    end
    return s
  end
  local top = {}
  for _ = 1, 3 + r(4) do top[#top + 1] = new_spec(0, false) end
  -- dedupe identical tables at top level (a table listed twice top-level is fine but noisy)
  if perm_seed then
    local pr = rng(perm_seed)
    for i = #top, 2, -1 do
      local j = pr(i)
      top[i], top[j] = top[j], top[i]
    end
  end
  return top
end

function G.describe(seed, perm_seed, mode)
  return vim.inspect(G.make(seed, perm_seed, mode))
end
return G
