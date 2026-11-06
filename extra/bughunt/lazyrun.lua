vim.opt.rtp:prepend(os.getenv('LAZY') or vim.fn.expand('~/.local/share/nvim/lazy/lazy.nvim'))
local Config = require('lazy.core.config')
Config.setup({ spec = {}, install = { missing = false }, performance = { rtp = { reset = false } }, change_detection = { enabled = false }, checker = { enabled = false } })
local Spec = require('lazy.core.plugin').Spec
local scen = dofile(_G.arg[1])
for _, s in ipairs(scen) do
  local ok, spec = pcall(Spec.new, s[2](), { optional = false })
  if not ok then print('=== ' .. s[1] .. '\n  ERROR ' .. tostring(spec)) else
  local out = {}
  for name, p in pairs(spec.plugins) do
    local o = p.opts
    out[#out + 1] = name .. '<-' .. tostring(p.url or p.dir) .. ' deps=' .. vim.inspect(p.dependencies or {}, { newline = '' , indent = ''}) .. ((p.enabled == false) and ' ENABLED=false' or '') .. (p.lazy ~= nil and (' lazy=' .. tostring(p.lazy)) or '')
  end
  table.sort(out)
  local dis = vim.tbl_keys(spec.disabled); table.sort(dis)
  local msgs = {}
  for _, n in ipairs(spec.notifs or {}) do msgs[#msgs+1] = n.msg end
  print('=== ' .. s[1] .. '\n  ' .. table.concat(out, '\n  ') .. '\n  disabled: ' .. table.concat(dis, ',') .. (#msgs > 0 and ('\n  msgs: ' .. table.concat(msgs, ' | ')) or ''))
  end
end
