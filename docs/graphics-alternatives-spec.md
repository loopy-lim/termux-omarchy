# GPU·입력 대체 경로 설계

사용자 요청: 실사용 가능한 GPU·키보드·마우스·권한을 구현하고, 지원되지 않으면 가능한 방법을 나열하여 다음 경로로 이동한다.

## 실행 계약

- Android API 28 이상, ARM64, 일반 앱 UID, 기존 Alpine 3.22.6/Mesa 25.1.9 이미지.
- Android 출력 GLES와 게스트 앱 OpenGL을 별도로 표시한다. 파일 존재, 권한, offscreen 렌더, 데스크톱 전달은 각각 다른 증거다.
- 게스트가 소프트웨어 OpenGL을 사용할 수 있도록 같은 Mesa 빌드의 DRI frontend 패키지를 추가한다.
- 새 데스크톱마다 bounded child EGL/GLES 픽셀 검사로 `llvmpipe → softpipe → cairo`를 선택한다. Sway는 검증된 pixman/wl_shm 출력을 유지한다.
- 하드웨어 후보는 드라이버·transport·실제 렌더·출력 조건을 만족해야 한다. 미구현 경로를 환경변수만으로 지원 처리하지 않는다.
- 현재 세션을 자동 종료하지 않는다. Ctrl+Alt+Esc, Surface 복구, 사용자 데이터 보존 계약을 유지한다.
- 준비 화면에 대체 방법과 실제 Android 설정 이동을 제공한다. ADB/Shizuku/root/Device Owner는 조건 및 별도 준비 상태를 명확히 표시한다.
- VirGL Android NDK bridge는 고정 소스 빌드를 시도하고 성공/실패 근거를 보존한다. 크로스빌드만으로 GPU 실사용 완료라고 표시하지 않는다.
- 새로운 파일은 500줄 이하. 실기기 변경, 부트로더/펌웨어/루팅, 권한 자동 부여, 커밋/푸시는 이 작업에 포함하지 않는다.

## 검증

잘못된 JSON·UID·session token·software renderer·timeout은 보수적으로 처리한다. 앱 UID VM에서 실제 EGL 픽셀과 GTK OpenGL 창 전달을 확인하고 기존 입력·권한·Surface 회귀 전체를 실행한다. 실기기 검증이 없으면 그 사실을 기록한다.
