-- Dump the state of a real startup to $ZB_OUT, two schedules after UIEnter, then quit.
-- $ZB_TREE is replaced by <tree> in rtp so trees compare equal.
vim.schedule(function()
  vim.schedule(function()
    local tree = vim.env.ZB_TREE
    local sections = {}
    local function add(name, list, keep_order)
      if not keep_order then table.sort(list) end
      sections[#sections + 1] = '== ' .. name .. '\n' .. table.concat(list, '\n')
    end

    local ok, api = pcall(require, 'zpack.api')
    local status = {}
    if ok and api.get_plugins then
      for _, p in ipairs(api.get_plugins()) do status[#status + 1] = p.name .. '=' .. tostring(p.status) end
    end
    add('STATUS', status)

    local rtp = {}
    for _, p in ipairs(vim.opt.rtp:get()) do
      rtp[#rtp + 1] = (tree and p:sub(1, #tree) == tree) and ('<tree>' .. p:sub(#tree + 1)) or p
    end
    add('RTP', rtp, true)

    local mods, zmods = {}, {}
    for k in pairs(package.loaded) do
      if k == 'zpack' or k:match('^zpack%.') then zmods[#zmods + 1] = k else mods[#mods + 1] = k end
    end
    add('MODS', mods)
    add('ZPACK_MODS', zmods)
    add('G', vim.fn.getcompletion('g:', 'var'))

    local au = {}
    for _, x in ipairs(vim.api.nvim_get_autocmds({})) do
      au[#au + 1] = x.event .. '|' .. (x.group_name or '') .. '|' .. (x.pattern or '') .. '|' .. (x.desc or '')
    end
    add('AU', au)
    add('CMDS', vim.tbl_keys(vim.api.nvim_get_commands({})))

    local keys = {}
    for _, m in ipairs({ 'n', 'x', 'o', 'i', 'c', 't', 's' }) do
      for _, k in ipairs(vim.api.nvim_get_keymap(m)) do
        keys[#keys + 1] = m .. '|' .. k.lhs .. '|' .. (k.desc or '') .. '|' .. (k.rhs or (k.callback and '<cb>') or '')
          .. '|expr=' .. tostring(k.expr)
      end
      for _, k in ipairs(vim.api.nvim_buf_get_keymap(0, m)) do
        keys[#keys + 1] = 'buf:' .. m .. '|' .. k.lhs .. '|' .. (k.desc or '') .. '|' .. (k.rhs or (k.callback and '<cb>') or '')
      end
    end
    add('KEYS', keys)
    add('BUF', { 'filetype=' .. vim.bo.filetype, 'colors_name=' .. tostring(vim.g.colors_name) })
    add('MSG', vim.split(vim.fn.execute('messages'), '\n', { trimempty = true }), true)

    local f = assert(io.open(vim.env.ZB_OUT, 'w'))
    f:write(table.concat(sections, '\n'), '\n')
    f:close()
    vim.cmd('qa!')
  end)
end)
