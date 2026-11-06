return {
  { 'D1 dev=true spec under disabled parent, upstream top-level', function() return {
    { 'folke/snacks.nvim', opts = {} },
    { 'test/off', enabled = false, dependencies = { { 'folke/snacks.nvim', dev = true } } },
  } end },
  { 'P1 shared plenary table: lazy parent + eager parent', function()
    local plenary = { 'nvim-lua/plenary.nvim' }
    return { { 'test/a', event = 'BufRead', dependencies = { plenary } }, { 'test/b', dependencies = { plenary } } }
  end },
  { 'P2 shared plenary table: lazy parent + disabled eager parent', function()
    local plenary = { 'nvim-lua/plenary.nvim' }
    return { { 'test/a', event = 'BufRead', dependencies = { plenary } }, { 'test/b', enabled = false, dependencies = { plenary } } }
  end },
  { 'P3 shared table: dep of lazy parent + specs of disabled plugin', function()
    local t = { 'test/lib', opts = {} }
    return { { 'test/a', event = 'BufRead', dependencies = { t } }, { 'test/b', enabled = false, specs = { t } } }
  end },
  { 'P4 shared table: top-level + dep of lazy parent (eager by its own top-level listing)', function()
    local t = { 'test/lib' }
    return { t, { 'test/a', event = 'BufRead', dependencies = { t } } }
  end },
}
