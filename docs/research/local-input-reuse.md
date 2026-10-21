# 로컬 입력 프로젝트 재사용 조사

조사일: 2026-10-05. 범위는 `/Users/loopy/dev/ll3/KeyBridge`와 `/Users/loopy/dev/ll3/Andra`의 현재 소스 확인이었다. 두 경로 모두 이 작업 환경에 존재하지 않는다. 상위 `/Users/loopy/dev/ll3` 목록에서도 두 이름을 찾지 못했다. 따라서 해당 프로젝트의 `AGENTS.md`·`CONTEXT.md`·README·라이선스·입력 구현을 읽지 못했고, Git commit SHA와 작업 트리 상태도 확인할 수 없다. 이 문서는 두 프로젝트의 기능, API, 빌드 또는 기기 동작을 검증했다는 뜻이 아니다.

## 현재 확인한 Loopy Desktop의 경계

- [README](../../README.md)는 저장소를 기기 진단 도구와 VM 감사 결과의 단계로 규정하며 제품 앱과 Linux 런타임이 아직 없다고 명시한다. 코드 파일은 500줄 이내로 유지하고 책임이 늘면 모듈을 나누는 규칙도 이 파일에 있다.
- [기기 기능 감사](../device-capabilities.md)는 VM에서 키보드 기능과 가상 트랙패드 분류를 관찰했지만, 물리 키보드 전환, 실제 트랙패드 스크롤·제스처, 한글 전환을 검증하지 않았다. Caps 전송도 지정 evdev 장치의 DOWN/UP으로 확인되지 않았다.
- 같은 감사는 자체 창 키 처리, 전역 필터, 원시 evdev, 원래 이벤트 억제, Android 주입을 구분한다. VM의 `/dev/uinput` 장치 생성은 ADB 셸에서만 확인됐고 실제 키 이벤트나 일반 앱 권한은 확인되지 않았다.
- [Y900 점검 절차](../y900-test-checklist.md)는 실제 키 scan/keycode, 트랙패드 멀티터치, 일반 앱과 ADB/Shizuku 권한을 향후 각각 확인하도록 정했다. 현재 Y900 실기기 확인 기록은 없다.

## 재사용 판단

| 후보 | 현재 소스로 확인한 사실 | Loopy Desktop에 남은 판단 |
| --- | --- | --- |
| KeyBridge | 지정 경로 부재. 모듈, 공개 API, 이벤트 수명 관리, 권한 경로, 라이선스, commit SHA, dirty state 모두 미확인 | `OutputPipeline`, synthetic key-up, Shizuku, heartbeat는 과거 조사에서 나온 **검색 단서**일 뿐이다. 소스를 확보하면 키 down/up 균형, 취소·장치 분리 시 복구, 권한 없는 경로, Android 주입 어댑터를 확인해야 한다. |
| Andra | 지정 경로 부재. 입력 코어·Android 주입·설정 모듈, 라이선스, commit SHA, dirty state 모두 미확인 | Caps tap/hold 상태기계, 포인터·제스처 변환, 앱 경계와 확장 지점을 실제 코드에서 확인해야 한다. |

두 후보에서 Wayland 입력 백엔드나 Android/Wayland 공용 semantic input normalizer를 재사용할 수 있다는 근거는 아직 없다. Loopy에서 필요한 역할을 설계할 때에도 Android가 호스트로 남고 런타임은 독립이라는 제품 경계를 유지해야 한다. Caps 짧게 누르기 언어 전환·길게 누르기 탐색, 포인터/트랙패드 변환, 선택적 Shizuku 권한은 확인된 기존 구현이 아닌 검증 대상 요구사항이다. 원본 소스와 라이선스를 확인하기 전에는 코드를 복사하거나 의존성으로 채택하지 않는다.

이번 조사는 경로 존재 여부와 Loopy 문서만 읽었다. 후보 저장소의 빌드·테스트·설치·기기 실행은 하지 않았다. 후속 조사는 두 저장소의 실제 체크아웃 경로를 확인한 뒤 해당 경로의 Git SHA와 dirty state를 기록하고, 코드 경로·라인·라이선스를 근거로 이 표를 갱신해야 한다.
