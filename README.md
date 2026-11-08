# Deck Input Lift

Keep the text field visible when the Steam Deck keyboard opens in **Desktop Mode**.

[한국어 안내](README.ko.md) · [Download v0.1.2 preview](https://github.com/www622846/deck-input-lift/releases/tag/v0.1.2) · [Device verification](VERIFICATION.md) · [Report a bug](https://github.com/www622846/deck-input-lift/issues)

Deck Input Lift makes room for the existing Steam keyboard, then asks the app to scroll its original focused input into view. Close the keyboard and the app's window size is restored. It keeps Steam's keyboard, layouts and input methods.

**Early preview:** verified on one Steam Deck running KWin 6.7.3 / Wayland, the Korean Steam keyboard and Firefox 152.0.4 Flatpak. Other versions and apps need testing. This is a Desktop Mode tool; Gaming Mode is outside its current scope.

An optional [experimental Korean composition bridge](steam-hangul/README.ko.md) keeps Steam's existing keyboard UI and routes its Korean keys through libhangul. It has a separate installer and is not included in the v0.1.2 release. See its [device results and limits](steam-hangul/VERIFICATION.md).

## Install on Steam Deck

1. Switch to Desktop Mode.
2. Download **[deck-input-lift-0.1.2.zip](https://github.com/www622846/deck-input-lift/releases/download/v0.1.2/deck-input-lift-0.1.2.zip)** from the release assets and extract it. Use this installer archive for the complete installation.
3. Close the Steam keyboard. Open a terminal in the extracted `deck-input-lift` folder and run:

   ```bash
   bash install.sh
   ```

4. Select a browser text field, then press **Steam + X**. The window should fit above the keyboard and the focused input should scroll into view. Close the keyboard to restore the window.

No `sudo`, Decky Loader, or SteamOS read-only filesystem changes are required. The installer only installs a KWin script and a user service in your home directory. After an update, close the keyboard and log out/in to load the new KWin script.

Requirements:

- KDE Plasma / KWin, `kpackagetool5` or `kpackagetool6`, and matching `kwriteconfig`.
- For automatic input scrolling: Python 3, `dbus-python`, PyGObject, AT-SPI 2 and a systemd user session. These were already present on the tested Steam Deck.
- An app exposing an editable input through AT-SPI and implementing its `ScrollTo` interface.

If the scrolling dependencies are unavailable, the installer explains that only window resizing is enabled. The optional [browser helper](browser/) is an alternative; its Firefox build is unsigned and can only be installed temporarily through `about:debugging`.

If the KWin script does not activate, enable **Deck Input Lift** in System Settings → Window Management → KWin Scripts and apply. The standalone `.kwinscript` release asset installs window resizing only; use the full ZIP for the system scrolling helper too.

## Pause or uninstall

- **Meta + Ctrl + K** toggles resizing and restores the window when paused.
- Without a physical keyboard, close the Steam keyboard first, then disable Deck Input Lift in KWin Scripts settings.
- To uninstall, close the keyboard and run this from the extracted folder:

  ```bash
  bash uninstall.sh
  ```

The optional browser extension, if installed separately, must be removed through the browser's extension manager.

## How it works

The KWin script watches for Steam's keyboard window and fits the active app into the remaining screen area. It restores the app when the keyboard closes. A small user service receives the target app's process ID over session D-Bus and uses AT-SPI to scroll the focused editable component into view.

Flatpak can expose different process IDs for its Wayland window and accessibility proxy. The helper matches their unique Flatpak instance IDs so the request reaches the correct app instance.

It does not read typed values, passwords or the clipboard, and does not collect keystrokes or send data to a network service. It reads process ancestry and Flatpak instance metadata to identify the app.

## Compatibility and limits

- Steam's keyboard must appear as a KWin-managed window. Recognized titles currently include `Steam Input On-screen Keyboard`, `Steam Input 가상 키보드`, and `Steam Keyboard`, together with a Steam window class.
- KWin 5/6 compatibility code is present; only the KWin 6.7.3 Wayland setup listed above has been device-tested.
- Apps with large minimum window sizes, inaccessible inputs, unsupported scrolling, or conflicting tiling rules may need additional support.
- On older KWin versions, initial maximization state is inferred from geometry. On Wayland, the normal window size from before maximization may not be restored exactly.
- Desktop startup is configured, but a full logout/reboot was not part of the device test.
- Existing Korean text was preserved in the device test. During diagnosis, actual Steam keyboard mouse/touch input produced `거짓` in an isolated Firefox page, but the reporter subsequently confirmed the final-consonant problem still occurs. v0.1.2 is not a confirmed fix for that issue. An optional experimental bridge is being tested separately; other IME paths, individual websites, top-docked keyboards and display scales need further testing.

Details and measured results are in [VERIFICATION.md](VERIFICATION.md). Background research is in [RESEARCH.md](RESEARCH.md).

## Development

Node.js 18+ and Python 3 are sufficient to run the dependency-free tests and build release archives:

```bash
npm test
npm run build
```

The current suite has 31 JavaScript tests and 14 Python regression tests. KWin tests use a simulated API; the separate device test covers actual Firefox and Steam keyboard behavior. Only run the device-check tools against the dedicated test profile described in their source.

Generated archives are placed in `dist/` and built from an explicit file allowlist. Contributions and device compatibility reports are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE).
