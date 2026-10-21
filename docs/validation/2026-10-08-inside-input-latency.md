# 현재 내부 브라우저의 입력 지연

현재 설치 APK는 `1790152c9593ce835b2aaf4adbe18cd8a240a2870a8f1d52a03541f64c79f611`다. [설치20](../../build/diagnostics/y900-android-inside-product-update-20261008-20/receipt.json)은 update-only 설치와 설정132개·서비스·역할·마이크 거부·global Shizuku lifetime 보존을 확인했다. [최종 호스트 검사](../../build/deliverables/LoopyDesktop-2026-10-08-inside-frame-pacing-02-arm64/host-test-receipt.json)는191개 통과·실패0·오류0·skip0다.

이 설치본에는 같은 Connection actor가 부분 FRAME 송신 사이 현재 lease의 입력을 적용하는 partial writer가 들어 있다. 실제 Connection·Wire·Policy를 사용하는 호스트 회귀에서 FRAME 완료 이전 input apply와 FRAME 뒤 ACK 순서를 확인했다. OS·표시·입력 주입 경계는 doubles이므로 이 결과를 기기 raw FRAME 중 입력 적용이나 물리 반응 지연의 증거로 바꾸지 않는다. FD/peer/birth·lease/focus 검사, 마지막 write와 full flush, 정확한 frame retirement와 불확실한 cleanup의 quarantine를 유지한다. [구현 계약](../superpowers/specs/2026-10-08-inside-frame-input-pacing.md).

[기준5089 공개 시험03](../../build/diagnostics/y900-inside-input-pacing-device-20261008-03/receipt.json)과 [설치1790 공개 시험04](../../build/diagnostics/y900-inside-input-pacing-device-20261008-04/receipt.json)은 실제 InputState→Session의 합성 클릭·키 DOWN/UP을 사용했다. 각 이벤트의 device monotonic `_send` 시작부터 canonical ACK 검증 완료까지 관찰한 값은 다음과 같다.

| 이벤트 | 기준5089 시험03 | 설치1790 시험04 |
| --- | ---: | ---: |
| 클릭 DOWN |77.715ms |33.331ms |
| 클릭 UP |26.387ms |90.816ms |
| 키 DOWN |19.240ms |40.345ms |
| 키 UP |27.831ms |13.724ms |

각 설치본의4개 단일 관찰이며 모두 `raw_frame_incomplete=false`, 관찰 FRAME은 압축 전송이었다. 감소·증가가 섞여 있고 raw backpressure를 재현하지 않았으므로 정량 개선율·지연 분포·raw FRAME 대기 해소를 주장하지 않는다. 두 시험은 새로운 공개 DOM click/key 증가, 정상 CLOSED와 소유 process/window/task/display/scope/jar/reverse/server 정리 및 설정·서비스·역할 보존을 통과했다. ROOT의 ARM 게시→DOM 증가 관찰 시간은 게시·조회 비용을 포함하는 별도 시계의 값이며 위 device ACK 시간과 빼거나 합치지 않는다. 물리 장치와 GTK event ingress를 거친 입력은 아니다.

사용자는 설치1790 후 입력이 “확실히 좀 더 빨라졌다”고 보고했다. 이 체감은 주관적인 사용자 피드백으로 기록하며 위 단일 표본의 정량 개선 증거와 구분한다.

ACK는 여전히 같은 stream의 진행 중 FRAME 뒤에 기다릴 수 있고, 다음 키·UP도 Session의 ACK pacing을 기다린다. GTK main loop의 수신·inflate·owned bytes/Pixbuf/Cairo 복사, capture/codec 비용과 물리 input-to-photon·지속 최소60/목표144fps는 남아 있다. [control/media 계획](../superpowers/plans/2026-10-08-inside-control-media.md)은 향후 구현 계획이며 현재 별도 FD 전달·ACK 대기 분리·native/GPU 전달이 구현됐다는 뜻이 아니다.

## 이전5089의 raw 수신과 동기 writer 기록

관찰 APK5089와 [Google 시험10](../../build/diagnostics/y900-inside-chrome-canonical-trial-20261008-10/receipt.json)을 기준으로 한다. 같은2512×1592 RGBA 한 장은15,996,416 bytes다. raw frame8의 header→complete receive는1079.107ms, frame9는1007.871ms였다. 두 프레임의 소프트웨어 수신 표본이며 물리 click-to-photon 지연을 측정한 값은 아니다.

당시 AndroidInsideShell.Connection은 read/handle 이후 capture→whole Writer.response를 끝내야 다음 입력을 읽었다. O_NONBLOCK FD도 write/retry loop가 packet 전체를 완료할 때까지 actor를 반환하지 않았다. 따라서 이미 socket 반대 방향에 도착한 클릭·키를 bulk 전송 뒤 처리할 수 있었다. GTK도 같은 main loop에서 read/inflate/owned bytes/GLib.Bytes/Pixbuf를 처리한다. Session의 한 command ACK pacing은 다음 키·UP에도 대기를 추가할 수 있다. 기여율과 물리 입력 구간은 미확정이다.

5089에는 partial writer를 아직 적용하지 않았으며, 위 raw 표본을 설치1790의 성능으로 승격하지 않는다. 첫 수정 이후에도 command ACK는 같은 stream의 FRAME 뒤에 남으므로 빠른 키 입력 전체가 해결됐다고 주장하지 않는다. 후속 인증 control/media 분리, native decode/storage와 실제 GPU buffer 전달의 [설계와 회귀 gate](../superpowers/specs/2026-10-08-inside-frame-input-pacing.md)를 유지한다.
