return {
  { 'Q1 x certainly removed (top-level dep on disabled d) but also nested enabled=false', function() return {
    { 'test/a', dependencies = { 'test/y' } },
    { 'test/x', dependencies = { 'test/d' }, specs = { { 'test/y', enabled = false } } },
    { 'test/d', enabled = false },
    { 'test/q', dependencies = { { 'test/x', enabled = false } } },
  } end },
  { 'Q2 same without the nested x enabled=false', function() return {
    { 'test/a', dependencies = { 'test/y' } },
    { 'test/x', dependencies = { 'test/d' }, specs = { { 'test/y', enabled = false } } },
    { 'test/d', enabled = false },
  } end },
}
