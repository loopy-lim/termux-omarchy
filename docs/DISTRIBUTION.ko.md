# 배포 입력 준비

[English](DISTRIBUTION.md) · [설치](INSTALL.ko.md) · [권한과 정책](PERMISSIONS.ko.md)

`v0.1.0-alpha.2`는 소스 Git 트리와 분리된 실험용 바이너리 배포를 제공합니다.
**후보의 새 기기 GUI 수락 검증은 완료하지 않았으며
`fullFreshInstallVerified`는 `false`입니다.** 소스·빌드 검사, APK 서명,
Android 권한과 물리 수락은 각각 별도 근거입니다.

## NDK 없이 릴리스 자산 받기

[설치 안내](INSTALL.ko.md)의 고정 태그와 기본 사용자의 네이티브 ARM64 Termux
환경을 사용하며 Git·네이티브 Python 3가 먼저 있어야 합니다. 해당 소스 checkout에서:

```sh
python3 -B installer/verify.py
python3 -B tools/acquire_distribution.py --plan
export OMARCHY_ASSETS="$HOME/termux-omarchy-v0.1.0-alpha.2-assets"
python3 -B tools/acquire_distribution.py --output "$OMARCHY_ASSETS"
python3 -B installer/install.py --check --assets "$OMARCHY_ASSETS"
```

목록에는 프로젝트 릴리스 아티팩트 15개와 외부 입력 74개가 있습니다. 최종 트리에는
빌드용 Weston `.deb`를 넣지 않습니다. 88개 파일을 내려받고 로컬 패키지 manifest
2개를 해시 검증해 복사하여 정확히 90개 파일을 만듭니다. 프로젝트 아티팩트에는
런타임 페이로드, guard 바이너리, 정확한 APK·companion과 대응 소스 아카이브 2개가
있습니다. 외부 런타임 입력은 고정한 기본 번들과 도구 29개·IME 7개의 패키지·서명 쌍입니다.

출력은 소유한 디렉터리 아래의 새 절대 경로여야 하며 Termux 홈이 적합합니다.
기존·부분 출력은 보존하고 거부합니다. 다운로드 명령은 설치·압축 해제·데스크톱
시작·Android 권한 부여를 하지 않습니다. 측정한 최대 사용량이 아닌 준비 여유분으로
8 GiB 이상의 여유 공간을 계획하세요. [APK 동의, 누락된 네이티브 의존성과 명시적 새
설치](INSTALL.ko.md)를 이어서 진행해야 하며 자산 검사 성공만으로 설치되지 않습니다.

## 유지보수자 경로: 외부 빌드 입력 74개 준비

아래 호스트 명령은 이 저장소의 루트에서 Python 3.12 이상으로 실행합니다.
소스 체크아웃 밖에 새 비공개 작업 디렉터리를 만듭니다. 다음 방식은 macOS와
Linux에서 실제 경로를 구합니다. 기존 파일의 해시가 다르면 덮어쓰지 않고 중단합니다.

```sh
export PREP_DIR="$(python3 -B -c 'from pathlib import Path; import tempfile; print(Path(tempfile.mkdtemp(prefix="termux-omarchy-dist-")).resolve())')"
mkdir -m 700 "$PREP_DIR/downloads"
python3 -B installer/verify.py
python3 -B tools/fetch_dependencies.py --check
python3 -B - <<'PY'
import json, os, subprocess, sys
from pathlib import Path
catalog = {name: row for name, row in
           json.loads(Path('manifests/downloads.json').read_text())['artifacts'].items()
           if row['purpose'] != 'project-release-artifact'}
assert len(catalog) == 74
for artifact in sorted(catalog):
    subprocess.run([sys.executable, '-B', 'tools/fetch_dependencies.py',
                    '--fetch', artifact, '--directory', os.environ['PREP_DIR'] + '/downloads'],
                   check=True)
PY
```

외부 입력은 Omarchy Android 0.1.1 기본 번들, Weston 호스트 패키지, 게스트 도구
패키지 29개, IME 패키지 7개와 각 게스트 패키지의 분리 서명이 포함됩니다.
릴리스 준비 과정에서 74개를 모두 내려받아 크기와 SHA-256을 확인했습니다.
총 1,223,199,036바이트, 약 1.14 GiB이며 전체 설치 크기나 측정한 최대 사용량이 아닙니다.
앞으로 다운로드가 실패하면 고정값을 검토해야 하며 더 최신 패키지로 바꾸어
우회하면 안 됩니다. 반복 실행하면 일치하는 로컬 파일을 검증하고 재사용합니다.
다운로더는 압축 해제, 실행, 설치나 패키지 서명의 암호학적 검증을 수행하지 않습니다.

## 런타임 페이로드 준비

```sh
python3 -B tools/prepare_runtime_payloads.py --check \
  --weston-deb "$PREP_DIR/downloads/weston_14.0.2-3_aarch64.deb"
python3 -B tools/prepare_runtime_payloads.py \
  --output "$PREP_DIR/runtime" \
  --weston-deb "$PREP_DIR/downloads/weston_14.0.2-3_aarch64.deb"
```

워크플로 파일 15개, 네이티브 Weston 파일 87개, 게스트 연동 파일 11개,
IME 설정 파일 5개의 고정된 매니페스트와 결정적 페이로드 아카이브를 만듭니다.
검토한 공개 소스와 고정된 Weston 패키지만 사용하며, 개인 프로필이나 기존
루트 파일시스템은 입력으로 쓰지 않습니다. 아티팩트를 디스크에 기록한 뒤에만
`preparation.json`을 만듭니다. 출력 디렉터리가 이미 있으면 거부하므로 실패한
시도는 보존하고 새 출력 경로를 사용하세요. 두 명령 모두 런타임을 설치하거나
시작하지 않습니다.

## PRoot guard 빌드

Android NDK **27.1.12297006** 경로를 `GUARD_NDK_ROOT`로 지정하고 `make`,
`patch`를 준비합니다. guard의 대상은 Android ARM64 API 28이며 실행 환경도
해당 API 이상이어야 합니다. 이 빌더는 별도로 고정한 공개 소스 아카이브 3개를
받습니다. 이 파일들은 런타임 다운로드 74개 목록에 포함되지 않습니다.

```sh
python3 -B native/guard/build.py --check
python3 -B native/guard/build.py --prepare --output "$PREP_DIR/guard-source"
python3 -B native/guard/build.py --build \
  --ndk "$GUARD_NDK_ROOT" --output "$PREP_DIR/guard-build"
```

`arm64-v8a/proot`, `arm64-v8a/loader`, `arm64-v8a/libandroid-shmem.so`,
`receipt.json`, `guard-corresponding-source.tar.gz`를 함께 보존합니다.
guard 바이너리를 배포할 때는 대응 소스 아카이브와 라이선스 고지도 함께
제공해야 합니다. 포함된 빌더는 오프라인 재빌드와 수정한 라이브러리의 재링크도
지원합니다. [guard 안내](../native/guard/README.md)를 참고하세요. `BUILT`는
컴파일과 ELF 검사를 통과했다는 뜻이며 기기 실행 검증을 뜻하지 않습니다.
릴리스 guard는 대응 소스로 오프라인 재빌드했으며 바이너리 바이트가 일치했습니다.

## 전체 소스에서 Android 입력 앱 빌드

과거 APK 재구성과 별개로 새 미서명 APK를 빌드하는 경로입니다.
먼저 [빌드 요구사항](../input/full_build/README.md)을 확인하세요.
`ANDROID_SDK_ROOT`와 호환되는 `JAVA_HOME`을 지정해야 합니다. SDK에는 안내한
플랫폼, 빌드 도구, CMake, 명령줄 도구와 이미 동의한 라이선스가 있어야 합니다.
이 드라이버는 guard와 다른 Android NDK **29.0.14206865**를 사용합니다.

```sh
python3 -B input/full_build/driver.py plan
python3 -B input/full_build/driver.py prepare --work-dir "$PREP_DIR/input-source"
python3 -B input/full_build/driver.py all \
  --work-dir "$PREP_DIR/input-build" \
  --sdk-source "$ANDROID_SDK_ROOT" --java-home "$JAVA_HOME" --install-missing
```

`--install-missing`은 기존 라이선스 동의를 사용해 고정된 NDK를 내려받도록
허용합니다. 새 약관에 동의하거나 제공한 SDK를 수정하지 않습니다. 빌드 시도마다
새 작업 디렉터리를 사용하세요. 실제 빌드 결과를 확인해야 합니다.
`UNSIGNED_APK_BUILT_NOT_AUDITED`만 미서명 결과물이 만들어졌음을 나타냅니다.
새 후보는 배포 전에 소스·라이선스, 패키징된 DEX/JNI, 일치하는 companion 메타데이터와
서명을 검토해야 합니다. 미서명 결과물을 설치하거나 컴파일용 stub을 앱 코드로 쓰면
안 됩니다. 릴리스 APK는 별도로 서명한 후보이며 드라이버의 미서명 출력이 아닙니다.

빌드 성공 후 전체 대응 소스를 내보냅니다.

```sh
python3 -B input/full_build/archive.py create \
  --prepared-dir "$PREP_DIR/input-build" \
  --output "$PREP_DIR/termux-x11-source.tar.gz"
```

내보낸 소스 아카이브로 Android ABI 4종의 오프라인 빌드를 통과했습니다.
`BUILD.md`는 Git 소스 다운로드 없는 재빌드를 설명합니다. 오프라인 Gradle 해석에는
정확한 배포·의존성 캐시와 SDK·NDK가 필요합니다. 이 빌드 근거는 후보의 GUI나
물리 입력 수락을 검증하지 않습니다.

shared UID 앱에는 **GitHub Termux 서명 계열**과 호환되는 인증서가 필요합니다.
F-Droid와 Google Play 설치본은 서로 교환할 수 없습니다. 업스트림 개발 서명
식별자는 공개되어 있어 신뢰 가능한 배포자 인증이 되지 않으며, 인증서가 같아도
이 포크를 업스트림 공식 배포로 인증하지 않습니다.
[서명 식별자 안내](../input/full_build/SIGNING.md)를 참고하세요. 호환성을
강제로 맞추기 위해 기존 앱을 삭제하거나, 데이터를 지우거나, shared UID를
변경하지 마세요.

## 네이티브 Termux 요구사항 확인

검증한 소스 복사본에서, Android 기본 사용자의 **네이티브 ARM64 Termux 셸**로만
실행합니다. 네이티브 Python 3가 먼저 설치되어 있어야 합니다. Linux 게스트 셸,
다른 Android 사용자, 추적 중인 프로세스에서는 거부합니다. guard 때문에 데스크톱
런타임은 Android API 28 이상이 필요합니다.

```sh
python3 -B installer/native.py --check
# 보고된 누락 네이티브 패키지를 명시적으로 설치:
python3 -B installer/native.py --apply
python3 -B installer/native.py --check
```

apply는 기존 APT 키와 서명된 메타데이터를 사용합니다. 공식 X11 저장소 패키지가
없으면 추가하고 누락된 그래픽, 오디오, X11, Weston 의존성과 PRoot-Distro를
설치합니다. 먼저 거래를 시뮬레이션하고 모든 기존 패키지를 현재 버전에 고정하며,
제거와 업그레이드를 거부합니다. PRoot-Distro 5.8과 검토한 5.9.0을 지원하고
이후 버전은 별도 검토가 필요합니다. 전체 업그레이드, 전역 PIP 설치, 서비스 실행,
APK 설치, 개인 설정 가져오기는 하지 않습니다. 기존 의존성 고정값으로 설치할 수
없으면 중단하고 계획을 검토하세요.
일치하는 Termux:X11 companion은 정확한 APK와 함께 최종 배포 자산에서 별도로
처리합니다. 네이티브 요구사항 준비는 저장소의 임의 nightly companion을 설치하지
않습니다. 구성요소 설치 후에는 런타임이 `termux-x11` 실행 파일을 요구합니다.

## 신뢰와 Android 동의

SHA-256 고정값은 검토한 바이트와의 일치를 보여주며 패키지 서명자를 증명하지
않습니다. 내려받은 `.sig`는 게스트가 이미 신뢰하는 Arch Linux ARM 키링으로
검증되어야 합니다. 설치기는 신뢰된 서명을 요구하며 임의의 키를 가져오거나
서명 검사를 끄지 않습니다. 네이티브 APT 신뢰와 APK 인증서 호환성도 별도 확인입니다.

기기 설치를 수락하기 전에 다음을 확인하세요.

1. 정확한 서명 APK, 소스·빌드 결과, companion과 인증서를 검토합니다.
   설치된 Termux 계열과의 호환성을 확인하고 앱 데이터를 보존합니다.
   런타임 자산은 해당 APK와 정확히 일치해야 합니다.
2. Android 설정에서 필요한 앱 설치, 키보드·입력기, 접근성 동의를 완료합니다.
   사용하려고 검토한 서비스와 매핑만 활성화하세요. Caps remapper 협력 기능은
   기본으로 꺼져 있습니다. 다른 기기의 opt-in marker나 매핑은 이식 가능한 설정이
   아닙니다.
3. OEM 단축키 정책, 백그라운드 프로세스 제한, ADB/Shizuku 작업은 각각 명시적으로
   선택합니다. 원래 값을 기록하고 현재 펌웨어가 해당 설정을 실제로 읽는지 확인한
   뒤 복구 방법을 보존하세요. 준비 도구는 이런 권한을 부여하거나 Android 정책을
   바꾸지 않습니다.
4. 대상 기기에서 시작, 중지·재시작, 앱 복귀, 포인터 캡처, 키 누름·해제,
   터치패드 스크롤, 한글 입력, GPU의 실제 화면 출력, 들리는 오디오를 확인합니다.
   빌드 결과나 JNI 성공 값으로 이 검사를 대신할 수 없습니다.
   [권한 경계](PERMISSIONS.ko.md)를 참고하세요.

## 검토한 로컬 입력 묶기

유지보수자는 로컬 입력으로 같은 닫힌 트리를 구성할 수 있습니다.
`SIGNED_INPUT_APK`와 `INPUT_COMPANION_DEB`를 검토한 서명 APK와 일치하는 소스
빌드 companion의 절대 경로로 지정합니다.

```sh
python3 -B tools/prepare_distribution.py \
  --downloads "$PREP_DIR/downloads" --payloads "$PREP_DIR/runtime" \
  --guard "$PREP_DIR/guard-build" --apk "$SIGNED_INPUT_APK" \
  --companion "$INPUT_COMPANION_DEB" \
  --apk-source "$PREP_DIR/termux-x11-source.tar.gz" \
  --output "$PREP_DIR/installation-assets"
python3 -B installer/install.py --check --assets "$PREP_DIR/installation-assets"
```

구성 도구는 `manifests/distribution.json`의 정확한 해시만 허용합니다. 별도 APK
빌드는 바이트가 달라질 수 있으며 새 후보 검토가 필요합니다. 기대 해시를 자동
갱신하지 마세요. 배포하는 바이너리 버전마다 대응 소스와 고지를 함께 제공합니다.
명시적 네이티브 준비, Android 동의와 새 설치 적용은 [설치 안내](INSTALL.ko.md)를
따르세요. 패키징 결과가 런타임 시작·Android 권한·물리 수락을 뜻하지는 않습니다.
새 기기 수락을 실제로 완료할 때까지 `fullFreshInstallVerified: false`를 유지합니다.
