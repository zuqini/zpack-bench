local function counted(name, val)
  return function()
    _G.ENABLED_CALLS = _G.ENABLED_CALLS or {}
    _G.ENABLED_CALLS[name] = (_G.ENABLED_CALLS[name] or 0) + 1
    return val
  end
end
return {
  { 'E1 kickstart-ish: devicons function enabled + nested boolean enabled under disabled telescope', function() return {
    { 'nvim-tree/nvim-web-devicons', enabled = counted('devicons', true) },
    { 'nvim-telescope/telescope.nvim', enabled = false, dependencies = { { 'nvim-tree/nvim-web-devicons', enabled = true } } },
  } end },
  { 'E2 same, function throws', function() return {
    { 'nvim-tree/nvim-web-devicons', enabled = function() error('boom') end },
    { 'nvim-telescope/telescope.nvim', enabled = false, dependencies = { { 'nvim-tree/nvim-web-devicons', enabled = true } } },
  } end },
}
