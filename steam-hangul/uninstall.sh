#!/usr/bin/env bash
set -euo pipefail
systemctl --user disable --now deck-steam-hangul.service
rm -f "$HOME/.config/systemd/user/deck-steam-hangul.service"
for file in composer.py engine.py bridge.py patch.js discover.js README.ko.md VERIFICATION.md uninstall.sh; do
    rm -f "$HOME/.local/share/deck-steam-hangul/$file"
done
systemctl --user daemon-reload
echo 'Steam 한글 보강을 제거했습니다. 원래 입력 처리로 돌아갑니다.'
