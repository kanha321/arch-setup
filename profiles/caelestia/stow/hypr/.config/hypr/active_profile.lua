-- profile: caelestia
-- Upstream caelestia-dots hypr config (see notes/caelestia-dots-upstream.txt).
-- Local overrides live in ~/.config/caelestia/hypr-vars.lua (stowed from the caelestia package).
package.loaded["caelestia_dots"] = nil
local ok, err = pcall(require, "caelestia_dots")
if not ok then
    print("active_profile: " .. tostring(err))
end
