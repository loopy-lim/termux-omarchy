# Tablet Dev Lab

Y900 Omarchy 안에서 편집·저장·미리보기를 확인하는 작은 Bun + TypeScript 프로젝트입니다. 계정이나 npm 의존성은 필요하지 않습니다.

```sh
cd ~/Projects/tablet-dev-lab
bun run dev
```

브라우저에서 `http://127.0.0.1:4173`을 엽니다. `src/message.ts`의 문구를 VS Code에서 바꾸고 저장하면 페이지 제목에 바로 반영됩니다. 작업 메모는 브라우저의 localStorage에 저장됩니다. 서버는 loopback으로만 열립니다. 종료는 실행한 터미널에서 Ctrl+C입니다.

설치된 Bun: 공식 `bun-v1.4.3` Linux ARM64, `~/.local/bin/bun`. 새 터미널에서 `bun`을 못 찾으면 `~/.local/bin/bun run dev`를 실행하세요. 백그라운드 시험 서버가 이미 실행 중이면 같은 포트의 두 번째 서버를 띄우지 않아도 됩니다.

태블릿에는 별도 생성한 12초 1080p60 H.264 시험 영상 `video.mp4`가 함께 있습니다. 이 저장소 예제에는 큰 영상 파일을 포함하지 않습니다. 영상이 없어도 코드 편집과 메모 기능은 사용할 수 있습니다. 로컬 영상 검증은 YouTube 네트워크·광고·자동 코덱 선택 검증과 다릅니다.
