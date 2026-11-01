if status is-interactive
    # Commands to run in interactive sessions can go here

    # Terminal colours from Caelestia, only while the caelestia profile is active
    if string match -q '*"active": "caelestia"*' (cat ~/.local/state/profile-switcher/state.json 2>/dev/null)
        cat ~/.local/state/caelestia/sequences.txt 2>/dev/null
    end
end
