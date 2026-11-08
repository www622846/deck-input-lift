#!/usr/bin/env bash
set -euo pipefail
echo '먼저 Steam 키보드를 닫으세요. 창 복원 후 제거하려면 Enter를 누르세요.'
read -r
if [[ -f $HOME/.config/systemd/user/deck-input-lift-focus.service ]]; then
    systemctl --user disable --now deck-input-lift-focus.service
    rm -f "$HOME/.config/systemd/user/deck-input-lift-focus.service" "$HOME/.local/share/deck-input-lift/native/focus_guard.py"
    rm -f "$HOME/.local/share/deck-input-lift/native/process_group.py"
    systemctl --user daemon-reload
fi
for version in 6 5; do
    if command -v "kwriteconfig$version" >/dev/null && command -v "kpackagetool$version" >/dev/null; then
        "kwriteconfig$version" --file kwinrc --group Plugins --key deck-input-liftEnabled false
        for candidate in qdbus6 qdbus qdbus-qt5 /usr/lib/qt6/bin/qdbus /usr/lib/qt5/bin/qdbus; do
            if command -v "$candidate" >/dev/null; then
                "$candidate" org.kde.KWin /KWin reconfigure && break
            fi
        done
        "kpackagetool$version" --type KWin/Script --remove deck-input-lift
        echo '제거 완료. Focus Guard는 브라우저의 확장 관리에서 제거하세요.'
        exit 0
    fi
done
echo 'KDE 도구를 찾을 수 없습니다. 시스템 설정 → KWin 스크립트에서 제거하세요.' >&2
exit 1
