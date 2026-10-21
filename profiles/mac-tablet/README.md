# Mac 설정의 Y900 이식본

현재 Mac 설정을 읽어 만든 Linux용 사본입니다. 원본 Mac 설정은 수정하지 않았습니다.

- APK 기본 터미널은 zsh입니다. Powerlevel10k, Git 별칭, fzf/fd/bat/eza/zoxide, 제안·구문 강조와 JetBrainsMono Nerd Font를 포함합니다. `.zshrc`·`.tmux.conf`는 없는 경우에만 생성합니다.
- tmux는 Ctrl+A 접두사, H/J/K/L 패널 이동, `|`·`-` 분할, 마우스·스크롤, 1부터 시작하는 창 번호, 투명 배경·기존 색상을 적용합니다. 물리 Alt+1…9/0은 tmux 창 1…9/10입니다. Ctrl+A 다음 숫자도 가능합니다.
- 물리 Meta+1…9/0은 Sway 작업공간 1…9/10이며, Shift를 함께 누르면 현재 창을 보냅니다. Alt+C/V는 복사·붙여넣기로 유지합니다. Caps+숫자는 기능 키입니다.
- `nvim/`은 현재 AstroNvim 설정과 실제 Mac 플러그인 체크아웃의 소스 스냅샷입니다. Space 리더, astrodark, Telescope 검색과 기존 사용자 설정을 유지합니다. 다운로드·자동 설치는 시작 시 실행하지 않습니다.
- `yazi/`는 1:2:7 패널 비율과 J/K 미리보기 이동을 유지하며, 편집기를 Linux Neovim으로 연결합니다. Mac 전용 래퍼 대신 foot에서 미디어 탐색을 엽니다.

`.zshenv`, 인증 정보, 셸 기록, SSH 키, Mac SDK·Homebrew 경로, Darwin 실행 파일·네이티브 플러그인은 옮기지 않았습니다. Linux fnm/Bun/Flutter/JDK/Rust 도구 체인과 LSP·DAP 서버는 설치된 도구가 있을 때만 사용할 수 있습니다. Markdown 파서가 없는 현재 Linux 이미지에서는 render-markdown을 비활성화하고 일반 텍스트 편집을 유지합니다. ImageMagick/LuaRocks 이미지 확장, Discord, Claude CLI, tinymist 미설치 연동도 비활성화합니다. Office 문서 전용 편집기를 포함하지 않습니다.

플러그인 81개의 Git 추적 소스만 별도 번들로 옮겼고 `.git`·미추적 파일·Mac 라이브러리를 제외했습니다. 따라서 이 사본에서 Lazy의 Git 업데이트를 실행하려면 Linux 체크아웃을 별도로 준비해야 합니다. 각 소스 커밋·해시는 [출처 기록](../../docs/validation/2026-10-06-y900-tablet-fit/mac-nvim-source.json)에 있습니다.

`install.py`는 SHA256, 파일 경로, 크기 제한, 심볼릭 링크와 기존 파일을 검사합니다. 기존 파일과 내용이 다르면 덮어쓰지 않습니다. 원래 배포된 `init.vim`만 정확한 해시를 확인한 뒤 `init.vim.loopy-before-mac-profile`로 백업합니다. 사용자 지정 init.vim은 자동으로 이동하지 않습니다.

실기기 설치·검증 기록은 [최종 검증 문서](../../docs/y900-tablet-final.md)를 참고하세요.
