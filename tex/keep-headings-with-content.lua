--[[
keep-headings-with-content.lua — Pandoc Lua filter

Adds approximate LaTeX keep-with-next reservations before H2 and H3 headings
based on their neighbouring AST blocks. It does not wrap or rewrite content.

Optional scalar YAML metadata:
  layout_keep_headings_with_content: true
  layout_h2_needspace: 6
  layout_h2_before_h3_needspace: 10
  layout_h3_needspace: 8
]]

local defaults = {
  enabled = true,
  h2_needspace = 6,
  h2_before_h3_needspace = 10,
  h3_needspace = 8,
}

local minimum_needspace = 1
local maximum_needspace = 30

local function fail(message)
  error("keep-headings-with-content: " .. message, 0)
end

local function metadata_text(meta, key)
  local value = meta[key]
  if value == nil then
    return nil
  end
  return pandoc.utils.stringify(value)
end

local function parse_boolean(meta, key, fallback)
  local raw = metadata_text(meta, key)
  if raw == nil then
    return fallback
  end

  local normalised = raw:lower()
  if normalised == "true" then
    return true
  end
  if normalised == "false" then
    return false
  end
  fail("invalid " .. key .. ": expected true or false")
end

local function parse_needspace(meta, key, fallback)
  local raw = metadata_text(meta, key)
  if raw == nil then
    return fallback
  end
  if not raw:match("^%d+$") then
    fail(
      "invalid "
        .. key
        .. ": expected an integer from "
        .. minimum_needspace
        .. " to "
        .. maximum_needspace
    )
  end

  local parsed = tonumber(raw)
  if parsed < minimum_needspace or parsed > maximum_needspace then
    fail(
      "invalid "
        .. key
        .. ": expected an integer from "
        .. minimum_needspace
        .. " to "
        .. maximum_needspace
    )
  end
  return parsed
end

local function read_config(meta)
  return {
    enabled = parse_boolean(
      meta,
      "layout_keep_headings_with_content",
      defaults.enabled
    ),
    h2_needspace = parse_needspace(
      meta,
      "layout_h2_needspace",
      defaults.h2_needspace
    ),
    h2_before_h3_needspace = parse_needspace(
      meta,
      "layout_h2_before_h3_needspace",
      defaults.h2_before_h3_needspace
    ),
    h3_needspace = parse_needspace(
      meta,
      "layout_h3_needspace",
      defaults.h3_needspace
    ),
  }
end

local function is_layout_wrapper(block)
  if block.t ~= "RawBlock" or block.format ~= "latex" then
    return false
  end
  return block.text == "\\begin{multicols}{2}"
    or block.text == "\\vspace{2pt}"
    or block.text == "\\end{multicols}"
end

-- The existing Core Capabilities filter emits LaTeX environment boundaries.
-- Look through those known wrappers, but treat other raw blocks as content.
local function next_structural_block(blocks, start_index)
  local index = start_index
  while index <= #blocks do
    local block = blocks[index]
    if not is_layout_wrapper(block) then
      return block, index
    end
    index = index + 1
  end
  return nil, nil
end

local function reservation(lines)
  return pandoc.RawBlock("latex", "\\cvneedspace{" .. lines .. "}")
end

function Pandoc(doc)
  local config = read_config(doc.meta)
  if not config.enabled then
    return doc
  end

  local blocks = doc.blocks
  local output = {}
  local suppressed_h3_index = nil

  for index, block in ipairs(blocks) do
    if block.t == "Header" and block.level == 2 then
      local next_block, next_index = next_structural_block(blocks, index + 1)

      if next_block ~= nil and next_block.t == "Header" and next_block.level == 3 then
        output[#output + 1] = reservation(config.h2_before_h3_needspace)
        -- The larger H2 reservation covers this H3 and its expected opening.
        -- Suppress only this immediately following H3; later H3s remain guarded.
        suppressed_h3_index = next_index
      elseif next_block ~= nil and next_block.t ~= "Header" then
        output[#output + 1] = reservation(config.h2_needspace)
        suppressed_h3_index = nil
      else
        suppressed_h3_index = nil
      end
    elseif block.t == "Header" and block.level == 3 then
      local next_block = next_structural_block(blocks, index + 1)
      if index ~= suppressed_h3_index
        and next_block ~= nil
        and next_block.t ~= "Header"
      then
        output[#output + 1] = reservation(config.h3_needspace)
      end
      if index == suppressed_h3_index then
        suppressed_h3_index = nil
      end
    end

    output[#output + 1] = block
  end

  return pandoc.Pandoc(output, doc.meta)
end
