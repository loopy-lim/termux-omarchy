# Loopy Desktop

Android 안에서 실행하는 Linux 데스크톱입니다. 앱 메뉴에서 편집기, 파일 관리자,
터미널, 시스템 모니터를 열고 여러 작업 공간으로 나눠 사용할 수 있습니다.

Files는 Android와 공유하는 `/mnt/shared` 폴더를 엽니다. 프로젝트는
`~/Projects`에도 보관할 수 있습니다. Editor는 Mousepad 그래픽 편집기이며,
Code와 CLI files는 각각 Neovim과 Yazi입니다. 터미널에는 Bash, Git, Python이 있습니다.

앱 메뉴의 Themes에서 Slate, Forest, Paper를 선택할 수 있습니다. 테마와
Android에서 선택한 단축키 조합은 다음 실행에도 유지됩니다.
사용자 창 배치와 키 설정은 `~/.config/sway/user.conf`, 터미널 설정은
`~/.config/foot/foot.ini`에 작성하면 테마를 바꿔도 보존됩니다.

기본 단축키는 `Keyboard.md`를 참고하세요. Android 앱도 앱 메뉴에서 열 수 있습니다.
