return {
  { 'S1 LazyVim: blink default + optional nvim-cmp spec nesting nvim-snippets; user disables friendly-snippets', function() return {
    { 'saghen/blink.cmp', event = 'InsertEnter', dependencies = { 'rafamadriz/friendly-snippets' } },
    { 'hrsh7th/nvim-cmp', optional = true, dependencies = { { 'garymjr/nvim-snippets', opts = {}, dependencies = { 'rafamadriz/friendly-snippets' } } } },
    { 'rafamadriz/friendly-snippets', enabled = false },
  } end },
}
