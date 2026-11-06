local function avante() return { 'yetone/avante.nvim', event = 'VeryLazy', dependencies = { 'hrsh7th/nvim-cmp' } } end
local function completion() return {
  'saghen/blink.cmp', event = 'InsertEnter',
  dependencies = { { 'rafamadriz/friendly-snippets', enabled = false } },  -- e.g. enabled = vim.g.snippets
  specs = { { 'hrsh7th/nvim-cmp', enabled = false } },                    -- "using blink turns nvim-cmp off"
} end
return {
  { 'B1 lua/plugins/avante.lua sorted before completion.lua', function() return { avante(), completion() } end },
  { 'B2 completion.lua before avante.lua (e.g. file renamed to zz-avante.lua)', function() return { completion(), avante() } end },
}
