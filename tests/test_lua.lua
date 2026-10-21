-- Run from the repository root with lua5.1, luajit or nvim -l: lua tests/test_lua.lua
local defined, layers = {}, {}
rex = {
  action = function(def)
    defined[def.name] = def
  end,
  layout = {
    block = function(block)
      return { block = block }
    end,
  },
  session = {
    new_layer = function(args)
      layers[#layers + 1] = args
      return { block_ids = { "block:picker" } }
    end,
  },
}
package.path = "lua/?.lua;" .. package.path
local rextracto = require("rextracto")

local function same(actual, expected)
  assert(#actual == #expected, ("length %d, expected %d: %s"):format(#actual, #expected, table.concat(actual, " ")))
  for index = 1, #expected do
    assert(actual[index] == expected[index], ("[%d] %s, expected %s"):format(index, tostring(actual[index]), expected[index]))
  end
end

-- Flags come out sorted; Lua-only options are left out and values become strings.
same(
  rextracto.command_for({
    root = "/opt/rextracto",
    action = "pick",
    python = "/usr/bin/python3",
    bounds = { 0, 0, 1, 1 },
    grab_area = "recent",
    min_length = 3,
    fzf_unset_default_opts = false,
  }, "session:a", "block:b"),
  {
    "/usr/bin/python3", "/opt/rextracto/rextracto.py",
    "--fzf-unset-default-opts", "false",
    "--grab-area", "recent",
    "--min-length", "3",
    "session:a", "block:b",
  }
)

-- Running from a checkout, the module finds its own root.
same(rextracto.command_for({}, "s", "b"), { "python3", "./rextracto.py", "s", "b" })

rextracto.setup({ root = "/r" })
local action = assert(defined.rextracto, "setup defines the rextracto action")
assert(not pcall(action.run, {}), "fails without a focused pane")
action.run({ session_id = "session:a", block_id = "block:b" })
local layer = layers[#layers]
assert(layer.focus == true, "the picker takes focus")
same(layer.bounds, { 0.05, 0.05, 0.9, 0.9 })
same(layer.layout.block.options.command, { "python3", "/r/rextracto.py", "session:a", "block:b" })

rextracto.setup({ root = "/r", action = "pick", bounds = { 0.1, 0.2, 0.3, 0.4 } })
defined.pick.run({ session_id = "session:a", block_id = "block:b" })
same(layers[#layers].bounds, { 0.1, 0.2, 0.3, 0.4 })

rex.session.new_layer = function()
  return nil, "no window"
end
local ok, err = pcall(action.run, { session_id = "session:a", block_id = "block:b" })
assert(not ok and err == "no window", "reports Rex errors")

print("lua tests passed")
