local function A() return { 'test/p6', dependencies = { 'test/p2' } } end
local function B() return { 'test/p4', dependencies = { { 'test/p5', enabled = false } }, specs = { { 'test/p2', enabled = false } } } end
local function C() return { 'test/p6', specs = { { 'test/p4', enabled = false } } } end
local function D() return { 'test/p5', specs = { { 'test/p6', dependencies = { { 'test/p3', enabled = false } } } } } end
local function E() return { 'test/p4' } end
return {
  { 'O1 (seed164 shape, p7 level lifted) A then B', function() return { A(), B() } end },
  { 'O1b B then A', function() return { B(), A() } end },
  { 'O2 (seed251) C, D, E', function() return { C(), D(), E() } end },
  { 'O2b D, C, E', function() return { D(), C(), E() } end },
}
