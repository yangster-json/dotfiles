return {
  "dnlhc/glance.nvim",
  config = function()
    local glance = require("glance")
    glance.setup({
      border = {
        enable = true,
        top_char = "―",
        bottom_char = "―",
      },
      hooks = {
        before_open = function(results, open, jump, method)

          if #results == 1 then
            jump(results[1])
          else
            open(results)
          end
        end,
      },
    })

  end,
}
