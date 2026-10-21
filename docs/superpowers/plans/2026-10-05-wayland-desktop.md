# Loopy Desktop 제품 구현 계획

최신 사용자 승인: Omarchy 수준 화면·입력·Android 우선권 처리까지 구현. 실기기 수락은 추후. 이전 terminal-only 종료 기준은 철회됐다.

1. 실제 ARM64 Sway 화면을 기본 진입점으로 전환한다. 타일링·작업공간·앱/창 런처와 Linux GUI 앱을 제공한다.
2. Android 이전 키 필터와 Android 14+ pointer motion 소유권을 선택 가능한 접근성 서비스로 구현한다. 보이는 desktop focus 범위만 소유하고 paired-key를 유지한다.
3. Caps 한영/hold navigation, 두벌식/Android IME, 마우스·트랙패드·가로 스크롤·관성·다중 접점 제스처와 설정을 구현한다.
4. Foreground service와 headless native host로 Android 앱 전환/Surface 복귀 시 Linux 앱을 유지한다. 명시적 종료만 owned process tree를 정리한다.
5. 자동/수동 모드, Android 앱 카탈로그/런처, inner Sway clipboard, 영속 HOME과 공유 문서 제공자를 연결한다.
6. Deskweft의 현재 소스를 감사하여 기기별 입력 해제·입력 단계 구분·설정/IPC 소유 패턴을 적용한다. 원본 데이터·설정·키스토어를 가져오지 않는다.
7. 모듈별 host tests, native lifecycle tests, 전체 Java/APK 빌드와 코드 크기 검사. 자체 VM을 사용하는 실행 검사는 후보 해시별 기록하며 물리 Y900 검증과 구분한다.
8. 사용 가능한 데스크톱 APK와 한국어 사용 안내를 납품하고, 실제 구현/자동 검사/실기기 미수락 경계를 기록한다.

분담: 입력/clipboard/Deskweft 감사, native/service lifecycle, guest packages/UI/workers를 병렬 작업. root는 제품 Android UI, 모드·한국어·우선권·앱/파일 연동과 최종 빌드 통합을 소유한다. 모든 코드 파일 500줄 이내. 이 작업 폴더는 Git 저장소가 아니며 커밋·푸시는 요청되지 않았다.
