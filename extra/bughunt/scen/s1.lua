local function counted(name, val)
  return function()
    _G.ENABLED_CALLS = _G.ENABLED_CALLS or {}
    _G.ENABLED_CALLS[name] = (_G.ENABLED_CALLS[name] or 0) + 1
    return val
  end
end
return {
  { 'A1 LazyVim lang.go extra + mason disabled, dap/none-ls/lint not used', function() return {
    { 'neovim/nvim-lspconfig', dependencies = { 'mason-org/mason.nvim' } },
    { 'mason-org/mason.nvim', opts = { ensure_installed = { 'goimports' } } },
    { 'nvimtools/none-ls.nvim', optional = true, dependencies = { { 'mason-org/mason.nvim', opts = { ensure_installed = { 'impl' } } } } },
    { 'mfussenegger/nvim-dap', optional = true, dependencies = { { 'mason-org/mason.nvim', opts = { ensure_installed = { 'delve' } } }, { 'leoluz/nvim-dap-go', opts = {} } } },
    { 'nvim-neotest/neotest', optional = true, dependencies = { 'fredrikaverpil/neotest-golang' } },
    { 'mason-org/mason.nvim', enabled = false },
  } end },
  { 'A2 nested ordering: x disabled only under y, y removed', function() return {
    { 'test/a', dependencies = { 'test/x' } },
    { 'test/z', dependencies = { { 'test/y', enabled = false, specs = { { 'test/x', enabled = false } } } } },
  } end },
  { 'A3 enabled fn count when a sibling enabled spec is dropped', function() return {
    { 'test/x', enabled = counted('x', true) },
    { 'test/p', enabled = false, dependencies = { { 'test/x', enabled = true } } },
  } end },
  { 'A3b enabled fn count, dropped spec has function enabled too', function() return {
    { 'test/x', enabled = counted('x_top', true) },
    { 'test/p', enabled = false, dependencies = { { 'test/x', enabled = counted('x_nested', true) } } },
  } end },
  { 'A4 dropped nested name folds two plugins', function() return {
    { 'a/x' },
    { 'b/y' },
    { 'test/p', enabled = false, dependencies = { { 'b/y', name = 'x' } } },
  } end },
  { 'A5 blink.compat optional dependency (LazyVim coding.blink)', function() return {
    { 'saghen/blink.cmp', event = 'InsertEnter', dependencies = { 'rafamadriz/friendly-snippets', { 'saghen/blink.compat', optional = true, opts = {} } } },
  } end },
}
