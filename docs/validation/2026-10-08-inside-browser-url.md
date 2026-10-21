# Chromium 내부 연결과 초기 URL 전달

현재 설치 APK는 `1790152c9593ce835b2aaf4adbe18cd8a240a2870a8f1d52a03541f64c79f611`다. [설치20](../../build/diagnostics/y900-android-inside-product-update-20261008-20/receipt.json)은 설정132개·서비스·역할 보존을 통과했다. partial writer의 호스트 증거, 제한된 합성 ACK 표본과 사용자 체감 피드백은 [최신 입력 지연 기록](2026-10-08-inside-input-latency.md)으로 연결한다. 다음5089 결과는 당시 증거로 보존한다.

## 이전5089의 초기 URL 검증

당시 Y900/TB522FU 설치 APK는 `5089f5dd4868add6dcad8a778eed077588564252ecaae384439a8b1fa5005dc7`(388,083,014 B)이었다. [설치19](../../build/diagnostics/y900-android-inside-product-update-20261008-19/receipt.json)는 설정132개·입력 서비스·HOME/ASSISTANT/BROWSER 역할·마이크 거부·global Shizuku lifetime 보존을 통과했다. [패키징](../../build/deliverables/LoopyDesktop-2026-10-08-inside-browser-url-arm64/packaging-receipt.json)은 관련174 검사·실패0·오류0·skip0, 서명과 native7개의 이전 d74 대비 동일 바이트를 확인한다.

Chrome의 추가 native 입력 표면을 일반 WindowId로 검사하던 수정은 유지한다. [현재 Google 시험10](../../build/diagnostics/y900-inside-chrome-canonical-trial-20261008-10/receipt.json)은 준비 후20초·오류0·압축/raw frame9개·같은 Pixbuf source 선택9개·정상 CLOSED와 소유 자원 정리를 통과했다. Task266/display74는 시험 전용이다.

새 OPEN_URL12는 인증된 초기 요청에 ASCII HTTP(S) URL1..2048 bytes와 compact 선택을 추가한다. 빈 실행/기존 action1..11/cap127 바이트는 유지한다. 고정 org Chromium 대상만 URI를 받으며 URL 원문은 RAM에만 유지한다. stock Chromium의 한 URL 및 stock XDG desktop의 단일 terminal %u/%U 경로를 처리한다. 사용자 지정 프로필·private·추가 옵션·여러 URL은 기존 argv를 유지한다. Notion Web catalog entry는 같은 내부 브라우저 경로로 게시한다.

[현재 초기 URL 시험04](../../build/diagnostics/y900-inside-url-canonical-trial-20261008-04/receipt.json)는 실제 browser_launch→catalog→inside_window→OPEN_URL→Android ACTION_VIEW를 사용했다. 공개 nonce fixture는 GET1·JavaScript ready1을 받았다. 주소 입력 합성 없이 task269/display77에서 frame31개를 decode/copy/source 선택했고 정상 CLOSED1·task/display/input 해제·process/window/scope/jar·소유 adb reverse·HTTP server 정리를 통과했다. 기존 task·현재132 설정·서비스·역할·APK를 보존했다. 공개 HTTPS fetch와 Adreno830 Vulkan WebGL context가 확인됐지만 전체 화면 전달의 GPU·물리 FPS 증거는 아니다.

실패01의 empty reverse-list blank line과 실패02/03의 reverse 성공 stdout 가정은 ROOT 검사 도구 오류이며 원본 receipt를 보존했다. 실패02에서 성공한 own reverse pair는 [별도 정리01](../../build/diagnostics/inside-url-reverse-own-cleanup-20261008-01/receipt.json)로 제거했고 실패03/성공04는 직접 own cleanup을 완료했다. 실패를 제품 연결 성공으로 집계하지 않는다.

기존 내부 창 재사용/NAV13은 아직 구현하지 않았다. 실제 Notion 로그인·문서 편집·IME·clipboard 및 물리 마우스/키·장시간 사용은 미검증이다. 입력 지연과 전체 최소60/목표144fps 수락은 별도 작업으로 남는다.
