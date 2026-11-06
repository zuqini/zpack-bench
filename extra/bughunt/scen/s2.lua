return {
  { 'A2 a-file before z-file', function() return {
    { 'test/a', dependencies = { 'test/x' } },
    { 'test/z', dependencies = { { 'test/y', enabled = false, specs = { { 'test/x', enabled = false } } } } },
  } end },
  { 'A2b z-file before a-file', function() return {
    { 'test/z', dependencies = { { 'test/y', enabled = false, specs = { { 'test/x', enabled = false } } } } },
    { 'test/a', dependencies = { 'test/x' } },
  } end },
  { 'A2c optional parent instead of disabled (z top optional)', function() return {
    { 'test/a', dependencies = { 'test/x' } },
    { 'test/y', specs = { { 'test/x', enabled = false } } },
    { 'test/z', dependencies = { { 'test/y', enabled = false } } },
  } end },
  { 'A2d same as A2c, reordered', function() return {
    { 'test/z', dependencies = { { 'test/y', enabled = false } } },
    { 'test/y', specs = { { 'test/x', enabled = false } } },
    { 'test/a', dependencies = { 'test/x' } },
  } end },
}
