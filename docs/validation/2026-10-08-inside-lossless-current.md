# Android 내부 창 무손실 전송 — 2026-10-08

현재 설치 APK는 `1790152c9593ce835b2aaf4adbe18cd8a240a2870a8f1d52a03541f64c79f611`다. [설치20](../../build/diagnostics/y900-android-inside-product-update-20261008-20/receipt.json)은 설정132개·서비스·역할 보존을 통과했다. partial writer의 호스트 증거, 제한된 합성 ACK 표본과 사용자 체감 피드백은 [최신 입력 지연 기록](2026-10-08-inside-input-latency.md)으로 연결한다. 아래5089·d74·무손실 후보 기록은 각 당시의 증거다.

## 이전5089 설치 상태

무손실 전송 소스를 포함한 당시 APK는 `5089f5dd4868add6dcad8a778eed077588564252ecaae384439a8b1fa5005dc7`였다. [연결과 URL 보고서](2026-10-08-inside-browser-url.md)와 [설치19](../../build/diagnostics/y900-android-inside-product-update-20261008-19/receipt.json)는 Google20초 기능 회귀 및 초기 URL 실제 페이지 로딩·정상 CLOSED 정리와 설정132 보존을 구분한다. Codec/Delivery/native7개는 이전d74와 같다. 초기 URL action12/client 경로만 추가됐고 legacy frame 바이트는 관련174 검사를 통과했다. [입력 지연](2026-10-08-inside-input-latency.md)의 당시 raw 수신 표본 약1초는 물리 latency/FPS 증거가 아니다. [이전 Google 시험08](../../build/diagnostics/y900-inside-chrome-canonical-trial-20261008-08/receipt.json)의27프레임은d74 당시 증거로 유지한다.

Chrome 추가 입력 표면의 포커스 검사 수정은 [별도 진단](2026-10-08-inside-chrome-input-surface.md)에 기록한다. 아래 53e52 후보·ART 독립 표본·이전 APK 기록은 당시 증거로 보존하고 현재 성능으로 승격하지 않는다.

## 이전 후보 기록

무손실 zlib 전송 후보 `53e52d290270602235ab8fb0e10b257de3e8d99ae7b2b95e599d1bb670505191`는 소스·호스트 검사·SDK 빌드·패키징 대조를 통과했다. **아직 설치하지 않았으며**, 설치된 제품은 `ae2c3c281f2d8133ed14260bd26044a4e6c5c8f70d6fc642bbeb30d8a6be40fc`다. [사용자 창 기록](../../build/diagnostics/y900-chromium-user-ready-20261008-01/receipt.json) 당시 Chromium task238/display51은 의도적으로 남겨 두었다. ROOT의 이후 11:35 수동 관찰에서는 그 창과 Chromium 프로세스가 없었지만 **원인은 미확정**이다. 사용자 종료·crash·OOM으로 분류하거나 이전 receipt를 수정하지 않는다. 이 관찰만으로 저장된 작업 상태나 업데이트 동의가 확인되는 것은 아니다.

같은 관찰에서 Loopy24510·Hyprland24667·소유 UserService32375/브로커 child32396은 유지되었다. 후보 설치·새 APK의 창 복원·복귀 geometry 시험은 여전히 미실행이다.

## 후보의 변경 범위

현재 입력과 약16MB RGBA 프레임이 같은 actor를 통과하는 경로에서 전송 바이트를 줄인다. 새 `OPEN_ZLIB=11`로 연결별 압축을 명시적으로 선택하고, `FRAME_ZLIB=7`의 bounded zlib payload를 기존 RGBA FRAME로 복원한다. 기본 Session의 OPEN1, 기존 FRAME4·VERSION1·capabilities127은 유지한다. 압축 거부를 legacy OPEN 자동 재시도로 우회하지 않는다.

압축이 이득이 없거나 시도 예산을 소진하면 같은 원본 RGBA의 FRAME4를 보낸다. 64KiB input/16KiB output 단위 사이에25ms 예산을 확인하며 native codec 호출 자체를 선점하지 않는다.25ms는 hard realtime 보장이 아니다. 한 in-flight 프레임과 정확한 lease/geometry/sequence retirement, FD·peer·birth·task·focus·입력·cleanup 검사를 유지한다. 압축 뒤 실제 소유 witness를 다시 확인하고 프레임을 offer한다.

Java Reader와 Python Decoder는 decoded 길이·checksum·EOF를 검증하며 잘린 stream, dictionary, trailing/연결된 stream, 출력 초과·부족을 거부한다. 픽셀 축소·색 변환·손실 압축이나 zero-copy 구현은 아니다. [계약](../superpowers/specs/2026-10-08-inside-lossless-frames.md), [최종 Codec](../../android/src/dev/loopy/desktop/AndroidInsideFrameCodec.java), [Delivery](../../android/src/dev/loopy/desktop/AndroidInsideFrameDelivery.java), [Python Decoder](../../android/assets/omarchy-bridge/inside_wire.py).

## 소스와 호스트 증거

| 증거 | 결과와 범위 |
| --- | --- |
| [최종 source freeze](../../build/deliverables/LoopyDesktop-2026-10-08-inside-lossless-arm64/source-freeze.json) | SHA`c483590dc88608b0a9193e104e1779c518c1a010a53dffcd2d1a78a439ae08da`,13개 소스·검사 파일 고정. Codec SHA`cb85f984013a7bb7797641e16cf884c8f58c55b125824e7314286efcaa2f81fd`. 독립 source-only 검토 PASS, 기기 성능 증거 아님. |
| [최종 host03](../../build/deliverables/LoopyDesktop-2026-10-08-inside-lossless-arm64/host-test-receipt.json) | SHA`831458f435befd44d3df33ffebf170870236c8dd12bc122218c535e40c575c16`,128개 PASS·실패0·오류0·skip0. malformed codec·raw fallback·legacy bytes·명시적 OPEN·현재 geometry 회귀를 구분한다. |
| [host benchmark02](../../build/deliverables/LoopyDesktop-2026-10-08-inside-lossless-arm64/host-benchmark-receipt.json) | SHA`9e11fe790b49ce3ffe1a97e544bfaba3d8ac3d9d0e19332d3f68c4d8f4e9fef2`,Java Writer→Python fragmented Decoder의 원본 픽셀 hash가 정확히 일치. 호스트 메모리 시험이다. |

초기 [host01](../../build/diagnostics/inside-lossless-host-tests-20261008-01/receipt.json)은72개 중2개 FAIL이다. 기존 View 검사의 OPEN1 기대와 명시적 OPEN_ZLIB 선택이 달랐으며 원본을 보존한다. 후속 host02는 이전 Codec SHA`2052a1d8…`이고, 이번 후보는 최종 Codec을 고정한 host03에 묶는다. [legacy Java suite01](../../build/diagnostics/inside-lossless-java-tests-20261008-01/receipt.json)의 Wire29·Policy42·Session93·SendGuard106 assertions도 이전 Codec 소스 기록과 구분한다.

## 호스트 바이트·시간 표본

동일2512×1592 RGBA 원본은15,996,416바이트다. 공개 structured fixture와 noise fixture를 각각3회 측정했다.

| 표본 | payload / wire 바이트 | encode 시간 | 결과 |
| --- | --- | --- | --- |
| Structured |115,918 /116,064 |14.098–15.029ms | 무손실 압축 선택 |
| Noise |15,996,416 /15,996,554 |25.110–25.227ms | 시도 예산 뒤 raw fallback |

Python fragmented decode 표본은5.095ms였고 복원 픽셀 SHA는 원본과 같았다. Writer 시간은 호스트 메모리 출력이며 Android CPU·PRoot socket·GTK draw·실제 네트워크 전송 시간으로 사용하지 않는다. 바이트 감소가 ae2의 합성 명령 시간이나 물리 입력 지연을 개선했다는 실기기 증거는 아직 없다.

## 기기 ART 독립 표본

ROOT의 [ART benchmark03](../../build/diagnostics/inside-lossless-android-benchmark-20261008-03/receipt.json) SHA`aa34630d232a0ceb9da28c3c1072639c017bfd0faadc89175f72064e26805ea5`는 최종 Codec SHA`cb85f984…`를 고정한 **UID2000 standalone 실행**이다. 2512×1592 원본에서 structured3회는115,918B payload·encode7.887–8.808ms, noise3회는 raw fallback·encode25.081–25.312ms였고 모두 원본 픽셀이 정확히 일치했다. Java 메모리 decode 표본은 structured13.263–17.191ms, noise9.852–11.960ms다.

소유 benchmark jar를 제거했고 설치 APK ae2와 Loopy PID24510은 실행 전후 같았다. `candidate_installed=false`, `standalone_art_only=true`다. 이 결과는 새 APK 앱 UID의 codec 속도나 전체 socket→GTK→표시/input 시간, 물리60/144fps 합격이 아니다.

## 빌드와 패키징

[보존한 build receipt](../../build/deliverables/LoopyDesktop-2026-10-08-inside-lossless-arm64/build-receipt.json) SHA는`0000c80b83f5078d9003e6b65e5d2baf516d77149b94492400887cc4e2c717ac`다. API28/target36·ARM64 빌드 입력6,768개를 기록한다.

| 산출물 | SHA-256 | 크기 |
| --- | --- | --- |
| [app.apk](../../build/deliverables/LoopyDesktop-2026-10-08-inside-lossless-arm64/app.apk) |`53e52d290270602235ab8fb0e10b257de3e8d99ae7b2b95e599d1bb670505191` |388,074,741 B |
| [test.apk](../../build/deliverables/LoopyDesktop-2026-10-08-inside-lossless-arm64/test.apk) |`717a64df966a3fb6f7730295d65b272a900d209dc81ec9339e03d59d25154fc1` |139,667 B |

ROOT의 [packaging receipt](../../build/deliverables/LoopyDesktop-2026-10-08-inside-lossless-arm64/packaging-receipt.json) SHA`80ed7f767e2fd48f479ab7e91a9cfe0a2667118b822bb8c2557c4d02169712ee`는 PASS다.13개 frozen source와 빌드 입력, packaged Python assets2개, 서명 검증을 확인했고 ROOT는 DEX의 Codec·Delivery 포함도 확인했다. Native ELF7개는 설치된 ae2와 byte 동일하다. 이는 패키징 비교이며 현재 기기 성능 합격이 아니다. `candidate_installed=false`를 유지한다.

## 남은 수락

후속 d74의 저장 확인·update-only 설치와 같은 geometry에서의 Chrome 기능 시험은 위에 기록했다. 아래 후보 당시 미실행 경계와 구분한다. 기기에서는 실제 압축 선택/raw fallback·픽셀 동일성·decode/transmit/ACK 구간·입력/focus/resize/close·소유 자원 정리를 별도로 확인해야 한다. 물리 입력·물리 표시·지속60/144fps·전체 Omarchy 목표는 미완료다. 기존 [ae2 Chromium 보고서](2026-10-08-android-chromium-inside-current.md)의 성공·실패·시간 표본을 후보의 성능으로 물려받지 않는다.
