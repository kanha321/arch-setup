# Phase 2 findings (30 Oct 2026)
- Both shells run on one quickshell-git build.
- Caelestia: start `caelestia shell -d`, stop `caelestia shell -k`, health `qs -c caelestia ipc show` (255 when down). D-Bus: Notifications, StatusNotifierWatcher.
- DMS: start/stop `systemctl --user start|stop dms.service`, health `dms ipc --help` (255 when down), bar layer namespace `dms:bar`. D-Bus: Notifications, StatusNotifierWatcher, org.freedesktop.ScreenSaver, org.gnome.ScreenSaver.
- Wait on fixed D-Bus names only, never StatusNotifierHost-<pid>-<n>.
- Generated, never stow: ~/.config/hypr/scheme/current.lua, ~/.config/hypr/dms/*.lua, ~/.config/dconf/user, shell caches and state dirs.
- DMS theme toggle rewrites only ~/.local/state/dms/session.json and dconf color-scheme; no overlap with Caelestia theme files.
- Prereq outside repo: /etc/udev/rules.d/99-dri-gpu-names.rules
