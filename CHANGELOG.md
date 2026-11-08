# Changelog

## 0.1.2 — 2026-11-08 (preview)

- Request input scrolling once per window reservation instead of repeating it when typing changes the window caption.
- Ignore repeated accessibility focus notifications for the same editable field.
- Suspend the optional browser helper during DOM IME composition and resume after composition ends.
- Add regression tests for repeated focus, caption updates, composition events and cancelled pending scrolls.
- Add isolated-page tools for testing actual Steam keyboard mouse and touch input without capturing the screen or reading personal tabs.

These changes remove unnecessary scrolling that could interfere with an input method. The reporter confirmed normal input after installing this update. The exact `거짓` → `거지ㅅ` symptom was not reproduced in the isolated Firefox page, so this release does not establish a universal fix for Steam/IBus Hangul composition issues.

## 0.1.1 — 2026-11-08 (preview)

- Resize the active app around Steam's Desktop Mode keyboard and restore it on close.
- Recognize the Korean Steam keyboard title alongside the English titles.
- Use AT-SPI to scroll the original focused editable input into view without reading its value.
- Match Flatpak's separate Wayland and accessibility processes by instance ID.
- Install a desktop user service without `sudo` or SteamOS filesystem changes.
- Include an optional browser scrolling helper, uninstall script, tests and reproducible release archives.
- Verify the complete path on KWin 6.7.3 Wayland with Firefox 152.0.4 Flatpak and the Korean Steam keyboard.
