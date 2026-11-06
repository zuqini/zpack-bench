return {
  { 'R1 LazyVim catppuccin core + blink extra bare-name optional spec', function() return {
    { 'catppuccin/nvim', lazy = true, name = 'catppuccin', specs = { { 'akinsho/bufferline.nvim', optional = true, opts = function() end } } },
    { 'akinsho/bufferline.nvim', event = 'VeryLazy' },
    { 'saghen/blink.cmp', event = 'InsertEnter' },
    { 'catppuccin', optional = true, opts = { integrations = { blink_cmp = true } } },
  } end },
  { 'R2 fork url under disabled parent, upstream kept top-level', function() return {
    { 'user/repo', opts = {} },
    { 'test/p', enabled = false, dependencies = { { 'user/repo', url = 'https://github.com/fork/repo' } } },
  } end },
  { 'R3 dir under optional parent, upstream kept as dependency of lazy plugin', function() return {
    { 'test/lazyparent', cmd = 'Foo', dependencies = { 'user/lib' } },
    { 'test/opt', optional = true, dependencies = { { dir = '/tmp/zp-nonexistent/lib' } } },
  } end },
  { 'R4 dependency string bare name (LazyVim dap.core: dependencies = "mason.nvim")', function() return {
    { 'mason-org/mason.nvim', cmd = 'Mason' },
    { 'jay-babu/mason-nvim-dap.nvim', cmd = 'DapInstall', dependencies = 'mason.nvim' },
    { 'mfussenegger/nvim-dap', optional = true, dependencies = { { 'mason-org/mason.nvim', opts = { ensure_installed = { 'delve' } } } } },
  } end },
  { 'R5 bare-name dep only + optional real-url spec', function() return {
    { 'neovim/nvim-lspconfig', event = 'BufReadPre', dependencies = { 'williamboman/mason.nvim' } },
    { 'jay-babu/mason-nvim-dap.nvim', cmd = 'DapInstall', dependencies = 'mason.nvim' },
    { 'nvimtools/none-ls.nvim', optional = true, dependencies = { { 'mason-org/mason.nvim', opts = { ensure_installed = { 'impl' } } } } },
  } end },
  { 'R6 lazy parent, dep also listed under eager parent that is disabled', function() return {
    { 'test/lazyp', event = 'BufRead', dependencies = { 'test/dep' } },
    { 'test/eagerp', enabled = false, dependencies = { 'test/dep' } },
  } end },
  { 'R7 dep-only plugin listed under a kept plugin spec that sits under a disabled plugin', function() return {
    { 'test/k', event = 'BufRead' },
    { 'test/d', enabled = false, specs = { { 'test/k', dependencies = { 'test/lib' } } } },
    { 'test/other', cmd = 'X', dependencies = { 'test/lib' } },
  } end },
  { 'R8 name alias set only under optional parent; other plugin shares basename', function() return {
    { 'user/repo', opts = {} },
    { 'other/repo', event = 'BufRead' },
    { 'test/opt', optional = true, dependencies = { { 'user/repo', name = 'repo-user' } } },
  } end },
}
