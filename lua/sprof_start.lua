-- Prepended to a row's init: sample the whole startup with jit.profile and append raw stacks to $SPROF_OUT at exit.
local prof = require('jit.profile')
local lines = {}
prof.start('li1', function(th, n, vm)
  lines[#lines + 1] = n .. '\t' .. vm .. '\t' .. prof.dumpstack(th, 'F|', 40) .. '\t' .. prof.dumpstack(th, 'l', 1)
end)
vim.api.nvim_create_autocmd('VimLeavePre', { once = true, callback = function()
  prof.stop()
  local f = assert(io.open(vim.env.SPROF_OUT, 'a'))
  f:write(table.concat(lines, '\n'), '\n')
  f:close()
end })
