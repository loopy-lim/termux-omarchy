# 내부 Android 앱의 무손실 화면 전송

전체 Omarchy 목표의 성능 개선 단계다. 현재 ae2의 입력 명령과 약16MB RGBA FRAME은 같은 actor에서 순서대로 처리한다. 공개11의 합성 명령 시간은 물리 입력 지연이 아니며, 압축의 효과는 실제 바이트·codec 시간·동일 경로의 후속 측정으로 확인해야 한다. 현재 사용자용 Chromium task238/display51은 유지한다.

## 계약

- 기존 OPEN=1, 응답 FRAME=4, LIP1/LIR1 VERSION1, HELLO capabilities127과 모든 기존 바이트는 유지한다.
- 새 OPEN_ZLIB=11은 OPEN과 같은 자원·세션·sequence·target admission을 통과하며 연결별 선택을 바꾸지 않는다. 오래된 broker의 거부를 OPEN 자동 재시도로 우회하지 않는다.
- 응답 FRAME_ZLIB=7은 기존 FRAME metadata 뒤에 encoded_size의 big-endian int64를 붙인다. Frame.format은RGBA8888=1이고 bytes는 stride×height의 복원된 길이다. wire payload 길이는 encoded_size와 같고 원본보다 작아야 한다.
- Java Message.frame(Frame, byte[], boolean)만 압축 여부를 선택한다. 작은 화면 또는 추가 metadata8바이트까지 포함한 압축 이득이 없는 화면은 원래 FRAME4를 보낸다. level1 표준 zlib wrapper를 사용하며64KiB input/16KiB output 단위 사이에25ms 시도 예산을 검사한다. native call 자체의 preemption이나25ms hard realtime 보장은 아니다. 예산 소진·clock rollback은 원본 FRAME fallback이다.
- Python Decoder와 Java Reader는 완전한 packet을 검증하고 제한된 inflate 이후 원래 FRAME로 정규화한다. 픽셀은 완전히 같아야 한다. EOF, trailing/concatenated stream, dictionary, checksum, 길이 초과/부족을 거부한다. 복원 출력은 선언된 decoded bytes와 같은 길이여야 하며 Python은 초과 검출용1바이트까지만 추가 허용한다. 한 Decoder feed에서 FRAME 두 개를 팽창시키지 않는다.
- 기존 한 borrowed frame, 같은 stamp/lease/geometry/sequence retirement, partial packet poisoning, packet deadline, FD/peer/birth guard, input/focus/cleanup을 유지한다. 입력 검사나 task 관찰을 줄이지 않는다.
- Session의 기본 생성은 legacy OPEN이다. 실제 View는 새 APK의 broker와 같이 배포되는 compressed opt-in을 사용한다. 현재 사용자 설정·브라우저 프로필·역할·서비스는 변경하지 않는다.
- 코드 모듈500줄 이하. ROOT만 테스트/JDK/SDK/ADB 실행. Git 초기화·commit·push 없음.

## 증거

Java codec와 실제 Writer/Reader, Python 실제 Decoder/Session을 독립 fixture로 시험한다. malformed 압축과 큰 선언의 rejection, legacy bytes, OPEN_ZLIB admission, 일반 FRAME fallback, 서로 다른 언어 사이 바이트 복원을 검증한다. SDK 빌드와 APK asset/native byte 확인은 설치와 구분한다. 성능은 codec+wire 바이트 감소부터 측정하며 물리60/144fps·실사용 지연 합격으로 확대하지 않는다.

참조: [Java Deflater](https://docs.oracle.com/en/java/javase/17/docs/api/java.base/java/util/zip/Deflater.html), [Python bounded decompress와 EOF](https://docs.python.org/3/library/zlib.html).
