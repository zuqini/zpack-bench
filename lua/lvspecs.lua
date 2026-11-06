-- Builds a LazyVim-shaped spec list by parsing LazyVim's spec files as data
-- (Tree-sitter, nothing from them is executed). Literal tables, strings,
-- numbers and booleans are kept; top-level `local x = { ... }` tables are
-- shared by reference; functions become stubs. A function-form `enabled`
-- returns a fixed pseudo-random boolean derived from its source text.
-- usage: local build = dofile(this); local list, failed, mods = build(lv_root, mode, seed)
local MARK = '<expr>'

local function hash(s)
  local h = 5381
  for i = 1, #s do
    h = (h * 33 + s:byte(i)) % 2147483647
  end
  return h
end

local function unquote(text)
  local q = text:sub(1, 1)
  if q == '"' or q == "'" then
    return text:sub(2, -2)
  end
  local eq = text:match('^%[(=*)%[')
  if eq then
    return text:sub(#eq + 3, -(#eq + 3))
  end
  return text
end

local function convert(node, src, env, key)
  local t = node:type()
  local text = vim.treesitter.get_node_text(node, src)
  if t == 'string' then
    return unquote(text)
  elseif t == 'number' then
    return tonumber(text)
  elseif t == 'true' then
    return true
  elseif t == 'false' then
    return false
  elseif t == 'nil' then
    return nil
  elseif t == 'identifier' then
    if env[text] ~= nil then
      return env[text]
    end
    return MARK
  elseif t == 'parenthesized_expression' then
    return convert(node:named_child(0), src, env, key)
  elseif t == 'function_definition' then
    if key == 'enabled' then
      local v = (hash(text) + (_G.__LV_SEED or 0)) % 3 ~= 0
      return function() return v end
    elseif key == 'cond' then
      return function() return true end
    elseif key == 'opts' then
      return function() end
    end
    return function() end
  elseif t == 'table_constructor' then
    local tbl = {}
    local i = 0
    for child in node:iter_children() do
      if child:type() == 'field' then
        local name = child:field('name')[1]
        local value = child:field('value')[1]
        if value then
          if name then
            local k
            if name:type() == 'identifier' then
              k = vim.treesitter.get_node_text(name, src)
            else
              k = convert(name, src, env)
            end
            if k ~= nil and k ~= MARK then
              tbl[k] = convert(value, src, env, k)
            end
          else
            i = i + 1
            local v = convert(value, src, env, key == 'dependencies' and 'dependencies' or nil)
            tbl[i] = v
          end
        end
      end
    end
    return tbl
  end
  return MARK
end

local function parse_module(path)
  local f = assert(io.open(path, 'r'))
  local src = f:read('*a')
  f:close()
  local parser = vim.treesitter.get_string_parser(src, 'lua')
  local root = parser:parse()[1]:root()
  local env = {}
  local ret
  for child in root:iter_children() do
    local t = child:type()
    if t == 'variable_declaration' then
      local assign = child:named_child(0)
      if assign and assign:type() == 'assignment_statement' then
        local vars = assign:named_child(0)
        local vals = assign:named_child(1)
        if vars and vals and vars:named_child_count() == 1 and vals:named_child_count() == 1 then
          local name = vim.treesitter.get_node_text(vars:named_child(0), src)
          local v = vals:named_child(0)
          if v:type() == 'table_constructor' then
            env[name] = convert(v, src, env)
          end
        end
      end
    elseif t == 'return_statement' then
      local exprs = child:named_child(0)
      if exprs then
        ret = convert(exprs:type() == 'expression_list' and exprs:named_child(0) or exprs, src, env)
      end
    end
  end
  return ret
end

return function(lv_root, mode, seed)
  _G.__LV_SEED = seed or 0
  local base = lv_root .. '/lua/'
  local core = { 'lazyvim/plugins/init', 'lazyvim/plugins/coding', 'lazyvim/plugins/colorscheme',
    'lazyvim/plugins/editor', 'lazyvim/plugins/formatting', 'lazyvim/plugins/linting',
    'lazyvim/plugins/lsp/init', 'lazyvim/plugins/treesitter', 'lazyvim/plugins/ui', 'lazyvim/plugins/util' }
  local extras = {}
  for _, path in ipairs(vim.fn.glob(base .. 'lazyvim/plugins/extras/**/*.lua', false, true)) do
    extras[#extras + 1] = path:sub(#base + 1, -5)
  end
  table.sort(extras)

  local mods = vim.list_slice(core)
  if mode == 'all' then
    vim.list_extend(mods, extras)
  elseif mode == 'subset' then
    math.randomseed(seed)
    for _, m in ipairs(extras) do
      if math.random() < 0.3 then
        mods[#mods + 1] = m
      end
    end
  end

  local list, failed = {}, {}
  for _, m in ipairs(mods) do
    local ok, res = pcall(parse_module, base .. m .. '.lua')
    if ok and type(res) == 'table' then
      list[#list + 1] = res
    else
      failed[#failed + 1] = m .. ': ' .. tostring(res):sub(1, 120)
    end
  end
  return list, failed, mods
end
