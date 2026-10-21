# Y900 PRoot 보호 경로 적용과 재시작 확인

이 문서는 전용 PRoot 보호 경로의 최초 적용 기록이다. 최신 TMPDIR·한글 입력·포인터 및 shell 상태는 [후속 확인](2026-10-09-chromium-input-followup-device.md)에 기록했다.

Termux Omarchy 세션에 전용 PRoot 보호 경로를 실제 적용하고 재시작을 확인했다. 새 세션은 15초 관찰 후에도 `ready`였다. 물리 한글 조합, 체감 입력 지연, 전체 Omarchy 기능과 장시간 안정성은 아직 검증을 마치지 않았다.

## 실제 적용한 경로

기존 세션 `cd62fbb0-c017-4917-8d8b-b0d3ea6e1149`를 소유 프로세스 정리 확인(`terminationConfirmed: true`)과 함께 종료한 뒤, 관리 디렉터리의 `proot-guard`에 PRoot·전용 loader·공유 라이브러리를 설치했다. 전역 Termux PRoot, 브라우저 프로필, 배율 설정은 변경하지 않았다. 이전 runtime 소스와 설치 기록은 백업했다. [설치 기록](../../build/diagnostics/termux-omarchy-proot-guard-install-device-20261009-02/receipt.json)

보호판 PRoot SHA-256은 `bdb15a8388038e2d1211ab6dd4d35fdf0bf3d9550cd03b24031eb4ba1de8c5c2`다. runtime은 설치 파일·디렉터리의 소유권과 해시를 검사하며, 불완전하거나 변조된 보호 경로에서 기본 PRoot로 내려가지 않는다. 세션 중 보호 경로 선택이 바뀌어도 실행을 거부한다. `proot-distro --isolated`가 실행 환경을 다시 구성하므로 전용 PRoot 선택은 호스트 `PD_PROOT_BIN`, `PROOT_EXITKILL=1`과 `PROOT_LOADER`는 명시적인 guest `-e` 인자로 전달한다.

## 실기기에서 확인한 범위

- 재시작한 세션은 `6abdb3b7-9dfa-45d8-91c0-a20e637549ef`다. 실제 PRoot PID 13235의 실행 파일 해시가 위 보호판과 일치하며 EXITKILL 요청을 확인했다. 시작 직후와 15초 후 모두 같은 세션이 `ready`였다. [재시작 기록](../../build/diagnostics/termux-omarchy-proot-guard-restart-device-20261009-01/receipt.json)
- 화면은 1920×1280, Hyprland 배율 1.25, monitor refresh 응답 60 Hz로 유지됐다. 설정 오류 응답은 비어 있고 오디오·Android 설정 연결은 ready였다. Fcitx 프로세스는 한 개였으며 XMODIFIERS·Qt·SDL 입력 환경을 상속했다. 이 상태 확인은 물리 입력 지연이나 실제 새 프레임 FPS 측정이 아니다.
- 앞선 독립 수명 시험에서 자기 tracer가 만료될 때 `PROOT_EXITKILL=0`은 자식이 남고, `1`은 자식이 자동 종료됐다. 두 fixture의 정리도 확인했으며 당시 사용자 세션은 유지했다. 현재 Omarchy 세션의 tracer를 강제 종료하는 시험은 하지 않았다. [독립 수명 시험](../../build/diagnostics/termux-omarchy-proot-private-lifetime-device-20261009-01/receipt.json)
- 독립적인 `--isolated` guest 실행은 UID 1000, 보호 요청 true, 고정 공개 응답 `ISOLATED_PROOT_OK`로 통과했다. 당시 데스크톱 재시작과 전역 PRoot 교체는 없었다. [격리 실행 기록](../../build/diagnostics/termux-omarchy-proot-isolated-probe-device-20261009-01/receipt.json)
- 관련 호스트 검사 216개가 실패·오류·skip 없이 통과했다. 호스트 검사와 위 실기기 확인은 각각 별도 근거다. [호스트 검사 기록](../../build/diagnostics/termux-omarchy-proot-guard-integration-host-20261009-01/test-receipt.json)

## 남은 입력·브라우저 확인

Fcitx 생존과 환경 상속만으로 Hangul 조합·확정 입력을 확인했다고 할 수 없다. 물리 한/영 키·Ctrl+Space, Alt+Tab·Alt+Space·Esc·Caps+H/J/K/L, 키보드·마우스 체감 지연과 전체 Omarchy 사용은 후속 확인이 남아 있다. 기존 입력 수정의 당시 결과는 [입력 적용 문서](2026-10-09-input-update-device.md)에 보존했다.

보호판 설치 직전 Chromium 프로필 오류 대화상자 7개를 확인했다. 별도의 읽기 전용 검사에서 프로필 DB 여섯 개는 모두 SQLite `quick_check`를 통과했고 개인 브라우저 데이터는 기록하지 않았다. 이 결과로 대화상자의 원인이나 프로필 전체의 정상 동작을 확정하지 않는다. 브라우저 프로필은 초기화하지 않았으며 원인 조사는 진행 중이다. [DB 검사 기록](../../build/diagnostics/termux-omarchy-chromium-profile-inspect-device-20261009-01/receipt.json)

후속 임시 소켓 시험에서 guest `/tmp`의 bind는 `EACCES`(13)로 거부되고 `/run/user/1000`은 성공했다. `TMPDIR`만 `/run/user/1000`으로 지정한 첫 Chromium 실행은 공개 Xwayland 창 한 개와 오류 대화상자 0개를 확인했다. 배율 설정은 변경하지 않았다. 두 번째 창으로 전달하는 동작은 검사 중이며, 프로필 오류 전체의 해결이나 원인 확정으로 기록하지 않는다. [소켓 경로 시험](../../build/diagnostics/termux-omarchy-chromium-socket-path-probe-device-20261009-01/receipt.json), [첫 창 시험](../../build/diagnostics/termux-omarchy-chromium-private-tmp-probe-device-20261009-01/receipt.json)

## 업데이트 키트

[보호 runtime 업데이트 키트](../../build/deliverables/LoopyOmarchy-Runtime-guard-update-20261009-01.tar.gz)는 25개 파일, 175,074바이트이며 SHA-256은 `dc8663fc70627e88ee3faecedc1873337a946bb42e03e11108c5ecfc4e05697c`다. 전달 기록의 범위는 기존 관리 환경용 업데이트이며 `fullOmarchyInstaller: false`다. [전달 기록](../../build/diagnostics/termux-omarchy-proot-guard-update-kit-20261009-01/delivery-receipt.json)
