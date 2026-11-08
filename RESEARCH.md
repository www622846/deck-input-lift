# GitHub 조사 — 2026-11-08

요구사항: Steam Deck **데스크톱 모드**에서 가상 키보드가 열릴 때 브라우저의
검색창/입력칸을 가리지 않고 입력 내용을 보면서 타이핑한다.

아래 공개 프로젝트의 README를 확인했지만, 조사 범위에서는 **기존 Steam 키보드의
등장에 따라 대상 앱 창을 자동 축소·복원하고 웹 입력칸의 가시성을 보완하는**
설치 가능한 프로젝트를 확인하지 못했다. GitHub 전체에 없다는 의미는 아니다.

| 프로젝트 | 확인한 기능 | 요구사항과의 차이 |
| --- | --- | --- |
| [Better Handheld Keyboard](https://github.com/AdamLovattDevOps/better-handheld-keyboard) | KDE 데스크톱용 대체 키보드, 이동·크기·투명도 조절 | README에서 대상 입력칸을 자동으로 피하는 동작을 확인하지 못함. 기존 Steam 키보드를 대체하는 접근 |
| [OpenSwipe](https://github.com/itsdestin/openswipe) | Plasma/Steam 키보드의 스와이프 입력 | 입력 방식 개선이 주목적이며, 이 요구사항의 Steam 키보드 회피 동작은 확인하지 못함 |
| [4deus Mod](https://github.com/ptflp/4deus-mod) | Steam 키보드를 앱 위에 유지, 보조키 및 컨트롤러 매핑 | 키보드가 입력칸을 가리지 않도록 창 공간을 확보하는 기능은 확인하지 못함 |
| [BetterKeyboard](https://github.com/chenx-dust/BetterKeyboard) | 물리 키보드 사용자 편의 | 가상 키보드에 가려진 입력창 문제와 다름 |
| [IMBOARD](https://github.com/AnicetusCer/imboard) | KDE Wayland용 이동·크기·투명도 조절 키보드 | README는 일반 앱 형태를 설명하며, KWin 입력 방식 등록은 기본 경로에서 제외 |

구현 근거:

- [KDE KWin 스크립트 튜토리얼](https://develop.kde.org/docs/plasma/kwin/): 패키지 구조 및 사용자 범위 설치.
- [KWin API](https://develop.kde.org/docs/plasma/kwin/api/): 창 생성·활성화·숨김 이벤트, frameGeometry, setMaximize, clientArea.
- [KWin 6.0 Window 선언](https://github.com/KDE/kwin/blob/v6.0.0/src/window.h): API 버전 차이 및 최대화 상태 읽기 제약 확인.
- [AT-SPI Component.scroll_to](https://gnome.pages.gitlab.gnome.org/at-spi2-core/libatspi/method.Component.scroll_to.html): 원래 편집 요소를 컨테이너의 보이는 영역으로 스크롤.

실기에서는 한국어 Steam 키보드 제목이 `Steam Input 가상 키보드`로 표시되는 것을 확인해
인식을 추가했다. KWin 6.7.3 Wayland의 창 축소·복원을 확인했으며 Firefox 152.0.4 Flatpak
입력칸은 창만 축소하면 보이지 않는 사례를 재현했다. 이를 위해 AT-SPI 보조 기능을 추가했다.

기존 프로젝트의 소스를 복사하지 않았으며 이 프로젝트는 별도 구현이다.
