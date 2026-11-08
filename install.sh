#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ $(uname -s) != Linux || -z ${DBUS_SESSION_BUS_ADDRESS:-} ]]; then
    echo 'Steam Deck 데스크톱 모드에서 일반 사용자로 실행하세요.' >&2
    exit 1
fi
if [[ $EUID == 0 ]]; then
    echo 'sudo 없이 실행하세요.' >&2
    exit 1
fi
package_tool=''
config_tool=''
for version in 6 5; do
    if command -v "kpackagetool$version" >/dev/null && command -v "kwriteconfig$version" >/dev/null; then
        package_tool="kpackagetool$version"
        config_tool="kwriteconfig$version"
        break
    fi
done
if [[ -z $package_tool ]]; then
    echo 'KDE kpackagetool5/6 및 kwriteconfig5/6을 찾을 수 없습니다.' >&2
    exit 1
fi
if python3 -c 'import dbus, gi; gi.require_version("Atspi", "2.0"); from gi.repository import Atspi' >/dev/null 2>&1; then
    mkdir -p "$HOME/.local/share/deck-input-lift/native" "$HOME/.config/systemd/user"
    cp native/focus_guard.py "$HOME/.local/share/deck-input-lift/native/focus_guard.py"
    cp native/process_group.py "$HOME/.local/share/deck-input-lift/native/process_group.py"
    cp native/deck-input-lift-focus.service "$HOME/.config/systemd/user/deck-input-lift-focus.service"
    systemctl --user daemon-reload
    systemctl --user enable --now deck-input-lift-focus.service
    systemctl --user restart deck-input-lift-focus.service
else
    echo '접근성 스크롤 보조 기능을 사용할 수 없습니다. python-dbus, PyGObject, AT-SPI가 필요합니다.' >&2
    echo '창 크기 조절은 설치되며, 웹 입력칸 스크롤에는 browser/의 확장을 사용할 수 있습니다.' >&2
fi
if [[ -d ${XDG_DATA_HOME:-$HOME/.local/share}/kwin/scripts/deck-input-lift ]]; then
    "$package_tool" --type KWin/Script --upgrade ./kwin
else
    "$package_tool" --type KWin/Script --install ./kwin
fi
"$config_tool" --file kwinrc --group Plugins --key deck-input-liftEnabled true
for candidate in qdbus6 qdbus qdbus-qt5 /usr/lib/qt6/bin/qdbus /usr/lib/qt5/bin/qdbus; do
    if command -v "$candidate" >/dev/null; then
        if "$candidate" org.kde.KWin /KWin reconfigure; then
            echo '설치 완료. 브라우저에서 Steam+X로 키보드를 열어 확인하세요.'
            echo '일시 중지/복원: Meta+Ctrl+K. 업데이트했다면 키보드를 닫고 로그아웃/로그인하세요.'
            exit 0
        fi
    fi
done
echo '파일 설치 완료. 시스템 설정 → 창 관리 → KWin 스크립트에서 Deck Input Lift를 켜고 적용하세요.'
