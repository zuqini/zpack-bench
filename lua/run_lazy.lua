-- nvim -u NONE -l run_lazy.lua <lv_root> <all|subset> [seed]
local lv_root, mode, seed = _G.arg[1], _G.arg[2], tonumber(_G.arg[3] or '0')
local here = debug.getinfo(1, 'S').source:sub(2):match('(.*/)')
local list = dofile(here .. 'lvspecs.lua')(lv_root, mode, seed)
vim.opt.rtp:prepend(os.getenv('LAZY') or vim.fn.expand('~/.local/share/nvim/lazy/lazy.nvim'))
local Config = require('lazy.core.config')
Config.setup({ spec = {}, install = { missing = false }, performance = { rtp = { reset = false } },
  change_detection = { enabled = false }, checker = { enabled = false }, pkg = { enabled = false }, rocks = { enabled = false } })
local Spec = require('lazy.core.plugin').Spec
local spec = Spec.new(list, { optional = false })
local out = {}
for name, p in pairs(spec.plugins) do
  -- lazy.nvim's own rule (lazy/core/plugin.lua M.update_state, same on upstream main) for a plugin without an explicit `lazy`.
  local lazy = p.lazy
  if lazy == nil then
    lazy = (p._ and p._.dep or p.event or p.keys or p.ft or p.cmd) and true or false
  end
  out[#out + 1] = ('P %s lazy=%s'):format(name, tostring(lazy))
  for _, d in ipairs(p.dependencies or {}) do
    if d ~= name then
      out[#out + 1] = ('E %s -> %s'):format(name, d)
    end
  end
end
for name in pairs(spec.disabled) do
  out[#out + 1] = 'X ' .. name
end
table.sort(out)
io.write(table.concat(out, '\n'), '\n')
