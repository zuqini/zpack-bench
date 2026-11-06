local function core()
  return {
    { 'folke/lazy.nvim', version = false, lazy = true },
    { 'folke/snacks.nvim', priority = 1000, lazy = false, opts = {} },
    { 'neovim/nvim-lspconfig', event = 'BufReadPre', dependencies = { 'mason.nvim', { 'mason-org/mason-lspconfig.nvim', config = function() end } }, opts = { servers = {} } },
    { 'mason-org/mason.nvim', cmd = 'Mason', build = ':MasonUpdate', opts_extend = { 'ensure_installed' }, opts = { ensure_installed = { 'stylua', 'shfmt' } } },
    { 'nvim-treesitter/nvim-treesitter', event = 'VeryLazy', opts_extend = { 'ensure_installed' }, opts = { ensure_installed = { 'lua' } } },
    { 'folke/tokyonight.nvim', lazy = true, opts = { style = 'moon' } },
    { 'catppuccin/nvim', lazy = true, name = 'catppuccin', opts = {}, specs = { { 'akinsho/bufferline.nvim', optional = true, opts = function() end } } },
    { 'akinsho/bufferline.nvim', event = 'VeryLazy', opts = {} },
    { 'nvim-lualine/lualine.nvim', event = 'VeryLazy', opts = {} },
    { 'folke/which-key.nvim', event = 'VeryLazy', opts_extend = { 'spec' }, opts = { spec = {} } },
    { 'stevearc/conform.nvim', cmd = 'ConformInfo', dependencies = { 'mason.nvim' }, opts = {} },
    { 'mfussenegger/nvim-lint', event = 'BufReadPost', opts = {} },
  }
end
local function blink_extra()
  return {
    { 'hrsh7th/nvim-cmp', optional = true, enabled = false },
    { 'saghen/blink.cmp', event = { 'InsertEnter', 'CmdlineEnter' }, opts_extend = { 'sources.default' },
      dependencies = { 'rafamadriz/friendly-snippets', { 'saghen/blink.compat', optional = true, opts = {} } }, opts = {} },
    { 'catppuccin', optional = true, opts = { integrations = { blink_cmp = true } } },
  }
end
local function go_extra()
  return {
    { 'nvim-treesitter/nvim-treesitter', opts = { ensure_installed = { 'go', 'gomod' } } },
    { 'neovim/nvim-lspconfig', opts = { servers = { gopls = {} } } },
    { 'mason-org/mason.nvim', opts = { ensure_installed = { 'goimports', 'gofumpt' } } },
    { 'nvimtools/none-ls.nvim', optional = true, dependencies = { { 'mason-org/mason.nvim', opts = { ensure_installed = { 'gomodifytags', 'impl' } } } }, opts = function() end },
    { 'mfussenegger/nvim-lint', optional = true, dependencies = { { 'mason-org/mason.nvim', opts = { ensure_installed = { 'golangci-lint' } } } }, opts = {} },
    { 'stevearc/conform.nvim', optional = true, opts = { formatters_by_ft = { go = { 'goimports' } } } },
    { 'mfussenegger/nvim-dap', optional = true, dependencies = { { 'mason-org/mason.nvim', opts = { ensure_installed = { 'delve' } } }, { 'leoluz/nvim-dap-go', opts = {} } } },
    { 'nvim-neotest/neotest', optional = true, dependencies = { 'fredrikaverpil/neotest-golang' }, opts = { adapters = {} } },
  }
end
local function python_extra()
  return {
    { 'nvim-neotest/neotest', optional = true, dependencies = { 'nvim-neotest/neotest-python' }, opts = {} },
    { 'mfussenegger/nvim-dap', optional = true, dependencies = { 'mfussenegger/nvim-dap-python', keys = { { '<leader>dPt', function() end } }, config = function() end } },
    { 'linux-cultist/venv-selector.nvim', cmd = 'VenvSelect', ft = 'python', opts = {} },
    { 'hrsh7th/nvim-cmp', optional = true, opts = function() end },
    { 'jay-babu/mason-nvim-dap.nvim', optional = true, opts = {} },
  }
end
local function dap_core()
  return {
    { 'mfussenegger/nvim-dap', dependencies = { 'rcarriga/nvim-dap-ui', { 'theHamsta/nvim-dap-virtual-text', opts = {} } }, keys = { { '<leader>db', function() end } }, config = function() end },
    { 'rcarriga/nvim-dap-ui', dependencies = { 'nvim-neotest/nvim-nio' }, opts = {} },
    { 'jay-babu/mason-nvim-dap.nvim', dependencies = 'mason.nvim', cmd = { 'DapInstall' }, opts = {} },
  }
end
local function test_core()
  return { { 'nvim-neotest/neotest', dependencies = { 'nvim-neotest/nvim-nio' }, opts = {} } }
end
local function cat(...) local r = {} for _, l in ipairs({ ... }) do vim.list_extend(r, l) end return r end
return {
  { 'L1 core+blink+go+python, no dap/test core', function() return cat(core(), blink_extra(), go_extra(), python_extra()) end },
  { 'L2 + dap.core + test.core', function() return cat(core(), blink_extra(), go_extra(), python_extra(), dap_core(), test_core()) end },
  { 'L3 L2 + user disables mason (NixOS recipe)', function() return cat(core(), blink_extra(), go_extra(), python_extra(), dap_core(), test_core(), { { 'mason-org/mason.nvim', enabled = false } }) end },
  { 'L4 L1 + user disables catppuccin', function() return cat(core(), blink_extra(), go_extra(), python_extra(), { { 'catppuccin/nvim', enabled = false } }) end },
}
