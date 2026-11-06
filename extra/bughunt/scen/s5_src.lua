return {
  { 'R5 minimal: real url dep, bare-name dep, real url under optional parent', function() return {
    { 'test/a', dependencies = { 'mason-org/mason.nvim' } },
    { 'test/b', dependencies = 'mason.nvim' },
    { 'test/opt', optional = true, dependencies = { { 'mason-org/mason.nvim', opts = {} } } },
  } end },
  { 'R5-nooptional: same without the optional spec (what the PR re-derives to)', function() return {
    { 'test/a', dependencies = { 'mason-org/mason.nvim' } },
    { 'test/b', dependencies = 'mason.nvim' },
  } end },
  { 'R5-disabled parent variant', function() return {
    { 'test/a', dependencies = { 'mason-org/mason.nvim' } },
    { 'test/b', dependencies = 'mason.nvim' },
    { 'test/off', enabled = false, dependencies = { { 'mason-org/mason.nvim', opts = {} } } },
  } end },
  { 'R5-cascade variant (parent cascade-disabled)', function() return {
    { 'test/a', dependencies = { 'mason-org/mason.nvim' } },
    { 'test/b', dependencies = 'mason.nvim' },
    { 'test/c', dependencies = { { 'test/gone', enabled = false }, { 'mason-org/mason.nvim', opts = {} } } },
  } end },
}
