local H = require('probe_harness')
local scen = dofile(os.getenv('SCEN'))
describe('probe', function()
  it('runs', function()
    for _, s in ipairs(scen) do
      H.extra_out = s[3]
      H.run(s[1], s[2])
    end
  end)
end)
