#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ $(uname -s) != Linux || $EUID == 0 ]]; then
    echo '스팀덱 데스크톱 모드의 일반 사용자로 실행하세요.' >&2
    exit 1
fi
python3 - <<'PY'
import gi
gi.require_version('Soup','3.0')
gi.require_version('Atspi','2.0')
from engine import SteamHangulEngine
engine=SteamHangulEngine()
engine.close()
PY
mkdir -p "$HOME/.local/share/deck-steam-hangul" "$HOME/.config/systemd/user"
for file in composer.py engine.py bridge.py patch.js discover.js README.ko.md VERIFICATION.md uninstall.sh; do
    cp "$file" "$HOME/.local/share/deck-steam-hangul/$file"
done
cp deck-steam-hangul.service "$HOME/.config/systemd/user/deck-steam-hangul.service"
systemctl --user daemon-reload
systemctl --user enable --now deck-steam-hangul.service
systemctl --user restart deck-steam-hangul.service
echo '실험적 Steam 한글 보강 설치 완료. Steam 키보드를 닫고 다시 열어 적용하세요.'
echo '끄기: systemctl --user stop deck-steam-hangul.service'
echo '켜기: systemctl --user start deck-steam-hangul.service'
