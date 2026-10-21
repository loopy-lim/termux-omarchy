# 키보드와 창 관리

아래는 기본 Ctrl+Alt 조합입니다. Android 설정에서 Meta 또는 Alt로 바꾸면
해당 조합이 Ctrl+Alt를 대신합니다.

| 단축키 | 동작 |
| --- | --- |
| Ctrl+Alt+Enter | 터미널 |
| Ctrl+Alt+Space | 앱 메뉴 |
| Ctrl+Alt+E | 그래픽 파일 관리자 |
| Ctrl+Alt+Shift+E | 그래픽 편집기 |
| Ctrl+Alt+Shift+B | Linux WebKit 브라우저 |
| Ctrl+Alt+Shift+C | Geany 코드 편집기 |
| Ctrl+Alt+Tab | 열린 창 목록 |
| Ctrl+Alt+W | 작업 공간 목록 |
| Ctrl+Alt+Shift+T | 테마 선택 |
| Ctrl+Alt+1…9 | 작업 공간 전환 |
| Ctrl+Alt+Shift+1…9 | 창을 다른 작업 공간으로 이동 |
| Ctrl+Alt+H/J/K/L | 왼쪽/아래/위/오른쪽 창 선택 |
| Ctrl+Alt+Shift+H/J/K/L | 창 이동 |
| Ctrl+Alt+B / V | 가로/세로 분할 |
| Ctrl+Alt+Shift+Space | 창을 자유롭게 이동 |
| Ctrl+Alt+F | 전체 화면 |
| Ctrl+Alt+R | 창 크기 조절, H/J/K/L 사용 후 Escape |
| Ctrl+Alt+Shift+Q | 선택한 창 닫기 |

앱 메뉴는 이름을 입력해서 검색하고 방향키와 Enter로 선택합니다.
Escape는 메뉴를 닫습니다. 한글 입력과 클립보드는 Android와 연결됩니다.


## 태블릿에서 Mac 배열 사용

Android 메뉴 → 설정 → `Mac 배열 · 물리 Alt=Cmd, Meta=Option`을 켭니다.
Ctrl과 Fn의 위치는 유지하고, 스페이스바 옆 Alt가 Cmd, 기존 Meta가 Option이 됩니다.
Fn은 키보드 펌웨어가 처리하는 경우 앱에서 위치를 바꿀 수 없습니다.

- Cmd+C/V/X/A: 복사 / 붙여넣기 / 잘라내기 / 전체 선택
- Cmd+Z, Shift+Cmd+Z: 실행 취소 / 다시 실행
- Cmd+S/O/N/T/F/L/R/P/W: 저장 / 열기 / 새 문서 / 새 탭 / 찾기 / 주소 / 새로고침 / 인쇄 / 닫기
- Shift+Cmd+S/N/T: 다른 이름으로 저장 / 새 창 / 닫은 탭 다시 열기
- Cmd+방향키: 줄 또는 문서의 시작/끝, Shift를 함께 누르면 선택
- Option+좌우, Option+Backspace: 단어 이동 / 이전 단어 삭제
- Cmd+Enter/Space/Tab/쉼표: 터미널 / 앱 / 열린 창 / 설정
- Cmd+H/M: 현재 창을 숨김, ‘열린 창’에서 다시 선택
- Ctrl+Alt+Esc: 물리 키 기준 비상 입력 반납

터미널의 Cmd+C/V는 Ctrl+Shift+C/V로 전달됩니다. 물리 Ctrl+C는 실행 중단입니다.
각 Linux 앱이 제공하는 단축키 범위 안에서 동작하며, 네이티브 Mac 메뉴 전체를 재현하지는 않습니다.

현재 KeyBridge 프로필: Caps 탭은 언어 전환, Caps+H/J/K/L은 방향키,
Caps+Shift+H/J/K/L은 선택, Caps+1…0/-/=는 F1…F12,
Caps+D/F 또는 이미 변환된 F13/F14는 이전/다음 작업 공간입니다.

4K 태블릿에서는 기본적으로 최대 1920×1280(세로는 1280×1920)으로 렌더링합니다.
원본 해상도 옵션은 작은 글자와 추가 렌더링 부하를 허용할 때 사용합니다.
화면 배율은 별도로 더 키울 수 있습니다. 화면 테두리에서는 Android의 둥근 모서리와
카메라 영역을 피하도록 여백이 적용됩니다.

## 숫자 작업공간

Mac 배열에서는 물리 Meta+`1…9`로 작업공간을 전환하고, Meta+`0`은 작업공간 10입니다. `Shift`를 함께 누르면 현재 창을 해당 작업공간으로 보내며, 현재 작업공간은 유지합니다. Caps+숫자는 기존 F1…F10입니다. 일반 Ctrl+숫자는 앱으로 전달합니다.

물리 Alt+`1…0`은 tmux 내부 창을 전환합니다. `Ctrl+A` 다음 `1…0`도 사용할 수 있습니다. Alt+C/V는 Cmd 복사·붙여넣기를 유지합니다. 기본 Linux 창 조작용 Ctrl+Alt+숫자도 같은 동작입니다.
