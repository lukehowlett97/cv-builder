--[[
multicol-core-capabilities.lua — Pandoc Lua filter

Wraps the content of the "Core capabilities" section in a LaTeX
multicols{2} environment. Everything before and after is left untouched.

Usage:
  pandoc input.md --lua-filter=tex/multicol-core-capabilities.lua ...

Detection is case-insensitive: "Core capabilities", "core capabilities",
"CORE CAPABILITIES", etc. all match.
]]

local multicol_heading_text = "core capabilities"

-- Return a lower-case, single-space-normalised version of the plain-text
-- content of a Pandoc Inline list.
local function heading_text(blocks)
  local parts = {}
  for _, item in ipairs(blocks) do
    if item.t == "Str" then
      parts[#parts + 1] = item.text
    elseif item.t == "Space" then
      parts[#parts + 1] = " "
    end
  end
  local text = table.concat(parts):lower():gsub("%s+", " "):match("^%s*(.-)%s*$")
  return text or ""
end

function Pandoc(doc)
  local blocks = doc.blocks
  local new_blocks = {}
  local i = 1

  while i <= #blocks do
    local block = blocks[i]

    if block.t == "Header" and block.level == 2 then
      local text = heading_text(block.content)
      if text == multicol_heading_text then
        -- Emit the section heading itself
        new_blocks[#new_blocks + 1] = block

        -- Collect all blocks after this heading until the next heading
        -- at level 1 or 2 (or end of document)
        local collected = {}
        local next_i = i + 1
        while next_i <= #blocks do
          local b = blocks[next_i]
          if b.t == "Header" and b.level <= 2 then
            break
          end
          collected[#collected + 1] = b
          next_i = next_i + 1
        end

        -- Wrap collected content in multicols
        if #collected > 0 then
          new_blocks[#new_blocks + 1] = pandoc.RawBlock("latex", "\\begin{multicols}{2}")
          new_blocks[#new_blocks + 1] = pandoc.RawBlock("latex", "\\vspace{2pt}")
          for _, cb in ipairs(collected) do
            new_blocks[#new_blocks + 1] = cb
          end
          new_blocks[#new_blocks + 1] = pandoc.RawBlock("latex", "\\end{multicols}")
        end

        i = next_i  -- advance past the collected content
        goto continue
      end
    end

    new_blocks[#new_blocks + 1] = block
    i = i + 1
    ::continue::
  end

  return pandoc.Pandoc(new_blocks, doc.meta)
end