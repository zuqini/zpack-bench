return function(cfg_root)
  package.path = cfg_root .. '/lua/?.lua;' .. cfg_root .. '/lua/?/init.lua;' .. package.path
  local list, failed = {}, {}
  for _, dir in ipairs({ 'core', 'extra' }) do
    local files = vim.fn.glob(cfg_root .. '/lua/plugins/' .. dir .. '/*.lua', false, true)
    table.sort(files)
    for _, f in ipairs(files) do
      local m = 'plugins.' .. dir .. '.' .. vim.fn.fnamemodify(f, ':t:r')
      local ok, res = pcall(require, m)
      if ok and type(res) == 'table' then list[#list + 1] = res else failed[#failed + 1] = m .. ': ' .. tostring(res) end
    end
  end
  return list, failed
end
