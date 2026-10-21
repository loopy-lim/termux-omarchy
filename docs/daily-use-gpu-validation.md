# 입력·권한·GPU 구현과 검증

이 문서는 `430821...` APK의 이전 27/27 기록이다. 후속 Mesa GL·VirGL probe·입력 대체 경로는 [현재 대체 경로 검증](capability-fallback-validation.md)을 사용한다. 아래의 ‘현재’와 ‘미구현’ 표현은 이 전달물 시점의 범위다.

2026-10-06 구현 범위는 Android 일반 앱의 데스크톱 입력 소유권, 실사용 준비 화면, Android 호스트 EGL/GLES 합성과 복구다. Linux Sway·WebKit·Geany의 렌더링은 현재 pixman/공유 메모리 경로다. Linux 게스트 3D 가속은 미구현이며 Y900 물리 키보드·마우스·GPU 성능 수락은 아직 없다.

## 현재 전달물과 최종 검증

[설치 APK](../build/deliverables/LoopyDesktop-2026-10-06-gpu-daily-use-arm64.apk)는 ARM64, Android 9/API 28 이상, target SDK 36이며 325,067,893바이트(약 325MB)다. 이전 전달 파일을 덮어쓰지 않았다. 전체 검사를 통과한 빌드와 전달 APK의 크기·SHA-256이 같음을 [전달 영수증](../build/deliverables/LoopyDesktop-2026-10-06-gpu-daily-use-arm64.apk.receipt.json)에 기록했다. [해시 파일](../build/deliverables/LoopyDesktop-2026-10-06-gpu-daily-use-arm64.apk.sha256)과 [빠른 시작](desktop-quickstart-ko.md)을 함께 확인한다.

```text
APK SHA-256: 43082162634ed0b66a80df6b6a9ec196073042df6bfc6f4f286b68b6d90b967d
Test APK:    968edcd39a3b0d5a6785ab29a00bdcf7d85f6061b257736a345610b150a5831e
```

| 검증 | 최종 결과 | 기록 |
| --- | --- | --- |
| 호스트 정책·도구·회귀 | 150개 통과, ResourceWarning 오류 처리 | [호스트 출력](validation/2026-10-06-gpu-input-delivery-final-vm/host-tests.txt) |
| Rust Wayland 호스트 | 40개 통과 | [네이티브 출력](validation/2026-10-06-gpu-input-delivery-final-vm/native-tests.txt) |
| 일반 Android 앱 전체 VM | **27/27 통과**, API 36, UID 10224, SELinux `untrusted_app` | [최종 영수증](validation/2026-10-06-gpu-input-delivery-final-vm/receipt.json) |
| 제품 GLES 셰이더 probe | BGRA·stride·알파·클리핑·4096열·정밀도 fallback·context 반납 통과. VM shell UID | [별도 probe](validation/2026-10-06-gpu-input-delivery-final-vm/gles-probe.json) |
| 코드 크기 | 218개 소스 확인, 최대 499줄 | [크기 검사](validation/2026-10-06-gpu-input-delivery-final-vm/code-size.txt) |
| 소스와 APK 내용 | 빌드 입력 77개·네이티브 소스 27개·패키지 payload 5개 일치, 불일치 0개 | [입력 대조](validation/2026-10-06-gpu-input-delivery-final-vm/source-input-integrity.json), [빌드 영수증](validation/2026-10-06-gpu-input-delivery-final-vm/build-receipt.json) |

최종 앱 실행은 VM의 ANGLE/SwiftShader에서 `renderer=gles`를 확인했다. GPU 배경색 `ff1b4269`가 정확히 표시되고 Surface 교체 전·후 같은 Linux 세션과 GLES 출력을 유지했다. 이 실행의 교체 후 no-data 재시도 횟수는 0이며, 일시적인 3·3·성공과 영구적인 오류 3은 별도 [픽셀 읽기 호스트 회귀 3개](validation/2026-10-06-gpu-input-delivery-final-vm/surface-pixels-regression.txt)에서 검증했다.

비상 반납은 실제 VM 캡처 true에서 해제 완료를 관측했고 대기 시간은 3ms였다. Linux 종료의 캡처 반납 관측 대기는 6ms였다. 둘 다 이후 800ms 동안 자동 재캡처가 없었고, 종료된 Linux도 자동 재시작하지 않았다. AUTO는 실제 observer를 세 차례 갱신한 뒤에도 전체 화면·캡처가 false였으며, 명시적인 데스크톱 복귀는 같은 세션이었다. 이 시간은 VM의 검사 대기 시간이며 물리 입력 지연 측정이 아니다.

실제 SurfaceTexture consumer 폐기 후에는 출력 오류·조작 버튼·캡처 반납·자동 재연결 중단을 확인했다. 같은 Linux 세션의 명시적인 출력 복구 뒤 GLES와 PixelCopy의 기대/관측 색 `ff2468ac`가 일치했다. 종료 정리 중 요청한 재시작도 새 세션의 준비 완료 뒤 전체 화면으로 복구했다.

준비 화면을 설정에서 다시 열고 닫아도 세션은 유지됐으며 캡처 반납도 확인했다. 알림 권한은 부여하지 않은 상태로 기록했고 기본 홈 후보 등록만 확인했다. 실제 Android 권한 승인·기본 홈 역할 부여 성공으로 확대하지 않는다. 합성 generic 터치패드는 실제 Android callback 2개·캡처 false·같은 Thunar PID의 폴더 이동을 확인했다. captured 터치패드는 공개 View callback에 합성 접점을 전달한 시험이며 물리 장치 수락이 아니다. VM 몰입 모드 설정도 복원 확인됐다.

## 구현

- 실제 키보드·포인터의 첫 연결 시 준비 화면을 한 번 안내한다. 설정의 **실사용 준비 · 권한/진단**에서 다시 열 수 있다. 접근성 연결·Android 14 이상 모션 전달, 세션 알림·차단된 알림 채널, 선택적 배터리 예외·기본 홈 역할, 현재 그래픽 경로를 표시한다. 권한 승인은 Android의 사용자 승인 화면을 사용한다.
- 활성 전체 화면과 포커스가 있는 데스크톱에서 실제 마우스의 Android pointer capture를 요청한다. 장치 분리·포커스 상실·설정 대화상자·태블릿 전환에서 반납한다. 취소 뒤 늦게 도착한 캡처도 해제한다. 접근성의 절대 마우스 이벤트와 캡처 이벤트가 중복되지 않도록 전달 소스를 갱신한다.
- **Ctrl+Alt+Esc**는 눌린 입력을 해제하고 조작 버튼을 복원한다. Linux는 유지하며 데스크톱 버튼으로 복귀한다. 접근성 서비스 중단·재연결은 held 입력과 전달 상태를 정리한다. Linux 종료 시 복구 안내를 표시하고 사용자가 데스크톱을 누르면 새 세션을 시작한다. 종료 정리 중의 재시작 요청도 유지하고 새 세션의 준비 완료 뒤 전체 화면으로 진입한다.
- AUTO는 물리 키보드 또는 포인터가 있는 상태와 없는 상태 사이의 실제 dock 전환에만 반응한다. 장치 정보 갱신이나 캡처에 따른 source 변경은 전체 화면 진입을 다시 요청하지 않으므로 비상 반납 상태를 유지한다. 모든 물리 입력 장치를 분리한 뒤 다시 연결하면 새로운 dock 전환으로 처리한다.
- `SOURCE_MOUSE_RELATIVE`도 물리 마우스와 포인터로 분류한다. 같은 복합 키보드 장치의 source만 바뀌고 키보드 능력이 유지되면 held key를 보존한다. 장치 비활성화·입력 능력 상실·제거는 해당 눌린 입력을 해제하며, raw 터치패드를 마우스로 분류하지 않는다.
- Wayland 표면과 하위 표면을 순서대로 GPU 텍스처에 올리고 BGRA 변환·premultiplied alpha·클리핑을 처리한다. EGL/GLES 실패는 CPU로 복귀하고 이유를 진단한다. fragment highp가 없는 GLES2에서 1024픽셀 초과 출력·텍스처는 CPU를 사용한다. Surface 교체는 Linux 세션을 유지한다.
- GPU와 CPU 모두 출력할 수 없으면 Linux를 유지하고 화면 오류·조작 버튼을 보여준다. 자동 재연결은 중단하며 데스크톱 버튼으로 같은 세션에 다시 연결한다. 현재 실행 세션과 token·준비 파일을 함께 확인해 종료된 세션의 오래된 파일이 전체 화면을 복구하지 않게 한다.

## 검증의 구분

호스트 입력·권한 정책은 실제 Android 시스템 승인이나 물리 캡처의 증거가 아니다. Android VM의 Surface 시험은 일반 앱 UID와 SELinux `untrusted_app`에서 실행한다. SwiftShader VM은 GLES 경로의 실행·픽셀 정확도·수명 증거이며 실제 장치의 하드웨어 가속·프레임률·전력 증거가 아니다.

별도 GLES probe는 제품 셰이더로 BGRA·stride·알파·클리핑, 4096개의 교대 1픽셀 열, 낮은 정밀도의 CPU 복귀, 정상·오류 후 context 반납을 검사한다. 이 probe는 VM shell UID에서 실행하므로 일반 앱 Surface 시험과 구분한다.

## 실패를 보존한 기록

- GPU 검사 추가 후 기존 CPU APK에서는 `GPU renderer unavailable`로 실패했다. [CPU 검사 출력](../build/gpu-cpu-red-instrumentation.txt)은 새 검사가 기존 CPU 경로를 합격시키지 않음을 보여준다. 최초 실행은 준비 대화상자 때문에 시작이 막혔고, 테스트 VM에서 이를 닫은 뒤 다시 실행했다.
- 첫 GPU 후보의 [단일 GPU 검사](validation/2026-10-06-daily-use-gpu-first/receipt.json)는 통과했다. [첫 전체 검사](validation/2026-10-06-daily-use-gpu-integration-first/receipt.json)는 22/24로 실패했다. raw 터치패드 generic 전용 검사는 자동 캡처에 따른 captured 전달과 조건이 충돌했다. generic 검사에서는 캡처 반납을 기다리고 이벤트 수·동일 Thunar PID·실제 폴더 이동을 각각 확인하도록 고쳤다.
- Sway 종료는 IPC 응답 전에 연결이 끊길 수 있다. 종료 코드 0을 강제하던 검사를 실제 host 종료·복구 안내·새 세션 시작 확인으로 바꿨다. [복구 단일 검사](validation/2026-10-06-guest-exit-recovery-vm/receipt.json)는 이 조건으로 통과했다. 이 중간 APK의 통과를 최종 APK 전체 검사로 대신 쓰지 않는다.
- [출력 실패 첫 검사](validation/2026-10-06-surface-failure-recovery-vm/receipt.json)는 실패했다. 실제 test-owned SurfaceTexture consumer를 폐기하면 NDK 크기 조회가 0/오류가 되어 일반적인 geometry 대기 경로에 머물렀다. Android 출력 대상은 마지막 유효 크기를 유지하고 새 guest commit 없이도 producer 출력을 확인하도록 바꿨다. 그 결과 출력 실패를 headless·오류로 전달하며 Linux 연결을 유지한다. 일반 테스트 대상의 일시적인 0 크기 대기 동작은 유지한다.
- [출력 실패 보완 검사](validation/2026-10-06-surface-failure-final-vm/receipt.json)는 251ms에 오류·제어 버튼·포인터 반납을 기록하고 자동 재연결 차단과 같은 세션의 GLES 복구를 확인했다. 마지막 픽셀 조건이 이미 닫힌 시작 메뉴를 요구해 전체 케이스는 실패했다. 복구 후 지정한 Sway 배경색이 PixelCopy에 나타나는 조건으로 바꿔 실제 출력 성공을 확인한다.
- 마우스 캡처 허용 때 접근성 큐의 이전 버튼 해제 이벤트가 버려지는 경우를 host RED로 재현했다. 캡처 진입 때 이전 포인터 상태만 한 번 해제하고 키보드 modifier·새 captured drag는 유지하는 회귀를 추가했다.
- [26개 첫 통합 검사](validation/2026-10-06-gpu-daily-use-final-vm/receipt.json)는 25/26이었다. generic 접점 2개·동일 Thunar PID의 폴더 이동과 출력 실패·같은 세션 GLES 복구·정확한 복구 배경색·종료 중 재시작은 통과했다. 비상 탈출은 비동기 `releasePointerCapture()` 요청 직후의 즉시 상태를 검사해 실패했다. 해제 완료를 기다리고 800ms 동안 자동 재캡처되지 않는지 확인하도록 강화했다.
- [비동기 반납 보완 후 검사](validation/2026-10-06-gpu-daily-use-delivery-vm/receipt.json)는 26/26으로 통과했다. VM에서 실제 캡처 상태가 true였고 23ms 뒤 해제 완료·800ms 동안 재캡처 없음·동일 세션 복귀를 기록했다. 이 APK는 뒤이어 발견한 자동 모드의 장치 갱신 문제를 아직 포함하지 않아 최종 전달물과 구분한다.
- 후속 점검에서 AUTO가 장치 갱신마다 데스크톱 진입 의도를 다시 설정해 비상 반납을 취소할 수 있는 경로를 발견했다. `AutoDockPolicy`로 실제 dock 상태 전환을 구분해 일반 descriptor 갱신은 반납 상태를 유지하도록 수정했다.
- 마우스 캡처 후 `SOURCE_MOUSE`가 `SOURCE_MOUSE_RELATIVE`로 바뀌는 장치와 복합 키보드의 source-only 갱신을 구분했다. 상대 마우스 능력은 유지하고, 키보드 능력이 남은 갱신에서 held key를 불필요하게 해제하지 않도록 보완했다. 비활성화·능력 상실·장치 제거의 해제 경로는 유지한다. 새 APK의 실행 결과는 별도로 기록한다.
- [자동 모드 보완 후 첫 전체 검사](validation/2026-10-06-auto-gpu-daily-use-final-vm/receipt.json)는 26/27이었다. GPU·권한 화면·출력 실패 복구·자동 모드의 세 차례 갱신은 통과했다. Linux 종료 검사만 host 종료·복구 문구 직후 worker에서 캡처 상태를 즉시 읽어 실패했다. Android 캡처 반납은 별도 비동기 응답이므로 UI 스레드에서 최대 8초 안의 실제 반납 완료를 확인하고, 이후 800ms 동안 자동 캡처·Linux 재시작이 없는지 추가로 확인하도록 강화했다. 같은 경계의 권한 대화상자도 실제 반납 완료를 기다린다.
- [Linux 종료 캡처 회귀 검사](validation/2026-10-06-guest-exit-capture-regression-vm/receipt.json)는 기존 캡처 true, UI 스레드 관찰에서 4ms 뒤 반납 완료, 800ms 동안 자동 캡처·재시작 없음, 명시적인 새 세션 복구를 기록하며 통과했다. 이 단일 검사는 새 APK 전체 검사 결과를 대신하지 않는다.
- [종료 검사 보완 후 전체 검사](validation/2026-10-06-auto-gpu-daily-use-verified-vm/receipt.json)는 26/27이었다. 종료·권한 화면의 실제 캡처 반납과 800ms 유지, 출력 오류 복구, AUTO 갱신은 통과했다. GPU 검사는 교체 전 정확한 `ff1b4269` 색을 기록했으나 Surface 교체 직후 첫 PixelCopy가 `ERROR_SOURCE_NO_DATA(3)`로 실패했다. 이 코드는 [Android 문서](https://developer.android.com/reference/android/view/PixelCopy#ERROR_SOURCE_NO_DATA)에서 첫 buffer가 아직 없는 상태로 정의한다. 이 응답만 제한 시간 내 재시도하며 다른 오류·콜백 timeout과 지속적인 buffer 부재는 실패하도록 보완한다. 교체 후 실제 지정 색의 정확한 일치 조건은 유지한다.
- [픽셀 읽기 보완 후 GPU 단일 검사](validation/2026-10-06-gpu-first-buffer-regression-vm/receipt.json)는 교체 전·후 GLES와 정확한 배경색·같은 세션을 확인하며 통과했다. 이 실행의 `surface_replacement_no_data_retries`는 0이었다. 별도 [호스트 회귀](../tests/test_surface_pixels.py)는 일시적 3·3·성공의 실제 픽셀 반환, 치명적 오류의 즉시 실패, 지속적인 3의 6초 제한과 각 bitmap 반납을 검사한다. 이 호스트 시험과 단일 VM 결과를 최종 전체 검사로 대신하지 않는다.

## 실기기에서 남은 확인

[Y900 점검표](y900-test-checklist.md)에 물리 장치 연결·분리, Android 승인·거부·설정 복귀, 실제 pointer capture·OEM 예약 키, 절전·장시간 실행, 실제 GPU renderer·고해상도 글자·프레임률·전력을 기록한다. Android의 모든 권한을 앱이 자동 취득하거나 모든 OEM 예약 키를 회수하는 기능은 제공하지 않는다. 현재 CPU fallback과 GLES 출력의 성공을 Linux 앱 3D 가속으로 표현하지 않는다.

설계와 실행 항목은 [명세](superpowers/specs/2026-10-06-daily-use-gpu-design.md), [계획](superpowers/plans/2026-10-06-daily-use-gpu.md)에 있다.
