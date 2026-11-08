"""Match a Flatpak app's Wayland process and its accessibility D-Bus proxy.

Reads only Flatpak instance identity and /proc/<numeric-pid>/stat ancestry
metadata, never command arguments, process environments, or .env files.
"""
from pathlib import Path


def process_group(pid, proc_root="/proc"):
    original = int(pid)
    # Flatpak may reparent its separate accessibility proxy sandbox to systemd,
    # so the proxy and Wayland process have no common bwrap ancestor. Their
    # .flatpak-info metadata still has the same unique Instance/instance-id.
    try:
        section = ""
        metadata = Path(proc_root) / str(original) / "root/.flatpak-info"
        with metadata.open() as stream:
            for raw in stream:
                line = raw.strip()
                if line.startswith("["):
                    section = line
                elif section == "[Instance]" and line.startswith("instance-id="):
                    instance = line.partition("=")[2].strip()
                    if instance and len(instance) < 128:
                        return "flatpak:" + instance
    except OSError:
        pass
    current = original
    group = original
    seen = set()
    for _ in range(16):
        if current <= 1 or current in seen:
            break
        seen.add(current)
        try:
            data = (Path(proc_root) / str(current) / "stat").read_text()
            end = data.rindex(")")
            name = data[data.index("(") + 1:end]
            parent = int(data[end + 2:].split()[1])
        except (OSError, ValueError, IndexError):
            break
        if name in ("bwrap", "flatpak", "xdg-dbus-proxy"):
            group = current
        if name in ("systemd", "sshd", "tailscaled", "konsole", "bash", "zsh"):
            break
        current = parent
    return group
