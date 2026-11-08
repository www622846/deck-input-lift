# Contributing

Bug reports and compatibility improvements are welcome.

For a device report, include the SteamOS and KWin versions, X11 or Wayland session, Steam keyboard language, app name/version, and steps to reproduce. Explain whether window resizing, input scrolling, or restoration fails.

Run the existing checks before submitting a pull request:

```bash
npm test
bash -n install.sh uninstall.sh
npm run build
```

Avoid collecting typed text in diagnostics. The helper should use input focus, geometry and accessibility scrolling while leaving text and IME composition to the original app.

For a KWin or native helper change, also test on a real Desktop Mode session: focus an input below the future keyboard area, open Steam's keyboard, confirm that the original input is visible, then close the keyboard and confirm window restoration. Describe the tested environment in the pull request. Simulator tests do not establish device compatibility.

`tools/kwin-probe.py` uses distro `dbus-python` and PyGObject for temporary session-bus probes. `tools/firefox-device-check.py` is specific to an isolated local Firefox test profile; do not point it at personal browser sessions. These developer tools are not required for normal use.
