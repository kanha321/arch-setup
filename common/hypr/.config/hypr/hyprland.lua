-- Shared Hyprland config (stowed from ~/dotfiles/common/hypr)
local terminal = "kitty"
local mainMod = "SUPER"

hl.env("AQ_DRM_DEVICES", "/dev/dri/nvidia-dgpu:/dev/dri/intel-igpu")

hl.monitor({
    output = "",
    mode = "preferred",
    position = "auto",
    scale = 1,
})

hl.on("hyprland.start", function()
    hl.exec_cmd(terminal)
    -- bring back the shell of the last active profile (profile resume)
    hl.exec_cmd("$HOME/.local/bin/profile resume")
end)

hl.bind(mainMod .. " + Return", hl.dsp.exec_cmd(terminal))
hl.bind(mainMod .. " + SHIFT + Q", hl.dsp.window.close())
hl.bind("CTRL + ALT + SHIFT + Q", hl.dsp.exec_cmd("hyprctl dispatch 'hl.dsp.exit()'"))

-- Per-profile include (stowed by the profile switcher). Cleared first so a
-- reload always re-runs it instead of returning a cached module.
package.loaded["active_profile"] = nil
local ok, err = pcall(require, "active_profile")
if not ok then
    print("active_profile: " .. tostring(err))
end
