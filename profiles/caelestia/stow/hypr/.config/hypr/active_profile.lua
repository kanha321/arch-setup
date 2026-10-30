-- profile: caelestia
-- "caelestia:*" global-shortcut binds get added once their names are captured.

-- caelestia binds (global shortcuts exist only while the shell runs)
local function cae(name)
    return hl.dsp.global("caelestia:" .. name)
end
local keep = { locked = true, repeating = true }
hl.bind("SUPER + SPACE", cae("launcher"))
hl.bind("SUPER + D", cae("dashboard"))
hl.bind("SUPER + N", cae("sidebar"))
hl.bind("SUPER + X", cae("session"))
hl.bind("SUPER + comma", cae("nexus"))
hl.bind("SUPER + ALT + L", cae("lock"))
hl.bind("SUPER + SHIFT + S", cae("screenshotFreezeClip"))
hl.bind("SUPER + SHIFT + ALT + S", cae("screenshot"))
hl.bind("XF86MonBrightnessUp", cae("brightnessUp"), keep)
hl.bind("XF86MonBrightnessDown", cae("brightnessDown"), keep)
hl.bind("XF86AudioPlay", cae("mediaToggle"), { locked = true })
hl.bind("XF86AudioPause", cae("mediaToggle"), { locked = true })
hl.bind("XF86AudioStop", cae("mediaStop"), { locked = true })
hl.bind("XF86AudioNext", cae("mediaNext"), { locked = true })
hl.bind("XF86AudioPrev", cae("mediaPrev"), { locked = true })
-- Caelestia has no volume shortcut, so use wpctl directly
hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+"), keep)
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"), keep)
hl.bind("XF86AudioMute", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"), { locked = true })
hl.bind("XF86AudioMicMute", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"), { locked = true })
