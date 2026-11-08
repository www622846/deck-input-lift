"""Build deterministic, allowlisted archives without dependencies or secret files."""
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
VERSION = json.loads((ROOT / "package.json").read_text())["version"]
OUT = ROOT / "dist"
OUT.mkdir(exist_ok=True)


def archive(name, files):
    with ZipFile(OUT / name, "w", ZIP_DEFLATED) as bundle:
        for source, target in files:
            info = ZipInfo(target, date_time=(2026, 11, 8, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = (0o100755 if source.suffix == ".sh" else 0o100644) << 16
            bundle.writestr(info, source.read_bytes())
    print(OUT / name)


kwin = [ROOT / "kwin/metadata.json", ROOT / "kwin/metadata.desktop", ROOT / "kwin/contents/code/main.js"]
browser = [ROOT / "browser/manifest.json", ROOT / "browser/focus-guard.js"]
archive("deck-input-lift.kwinscript", [(p, p.relative_to(ROOT / "kwin").as_posix()) for p in kwin])
archive("focus-guard.zip", [(p, p.relative_to(ROOT / "browser").as_posix()) for p in browser])
release = kwin + browser + [ROOT / n for n in (
    "install.sh", "uninstall.sh", "README.md", "README.ko.md", "RESEARCH.md", "VERIFICATION.md", "LICENSE", "package.json",
    "CHANGELOG.md", "CONTRIBUTING.md",
    "tests/kwin.test.cjs", "tests/browser.test.cjs", "tests/browser-integration.py", "tools/package.py",
    "native/focus_guard.py", "native/deck-input-lift-focus.service",
    "native/process_group.py", "tests/test_process_group.py",
    "tests/test_focus_guard.py",
    "tools/kwin-probe.py", "tools/firefox-device-check.py",
    "tools/ime-web-probe.py", "tools/steam-keyboard-probe.mjs",
)]
archive(f"deck-input-lift-{VERSION}.zip", [(p, "deck-input-lift/" + p.relative_to(ROOT).as_posix()) for p in release])
assets = (f"deck-input-lift-{VERSION}.zip", "deck-input-lift.kwinscript", "focus-guard.zip")
(OUT / "SHA256SUMS.txt").write_text("".join(
    f"{hashlib.sha256((OUT / name).read_bytes()).hexdigest()}  {name}\n" for name in assets
))
