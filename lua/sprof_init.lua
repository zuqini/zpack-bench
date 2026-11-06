-- Sampling profile of one real startup; appends raw stacks to $SPROF_OUT. ZP_TREE = zpack tree.
local prof = require('jit.profile')
local lines = {}
prof.start('li1', function(th, n, vm)
  lines[#lines + 1] = n .. '\t' .. vm .. '\t' .. prof.dumpstack(th, 'F|', 40) .. '\t' .. prof.dumpstack(th, 'l', 1)
end)
local stop = function()
  prof.stop()
  local f = io.open(vim.env.SPROF_OUT, 'a')
  f:write(table.concat(lines, '\n'), '\n'); f:close()
end
vim.api.nvim_create_autocmd('VimEnter', { once = true, callback = stop })
vim.opt.rtp:prepend(vim.env.ZP_TREE)
require('zpack').setup({ defaults = { confirm = false } })
