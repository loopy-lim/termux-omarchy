# 원본 Omarchy 158개 요청을 위한 제한된 패키지 변경 후보

2026-10-09. **기존 패키지 4개 업데이트와 폰트 1개 교체를 허용하면, 고정 DB 안에서 원본 158개 요청의 전체 의존성이 해소된다.** 전체 후보는 아카이브 340개, 그중 기존 이름 업데이트 4개·새 이름 336개이며 기존 full Nerd Font 1개를 제거한다. 설치된 나머지 587개는 현재 버전을 그대로 유지한다. 최종 예상 패키지 수는 927개다. 이 문서는 오프라인 metadata 후보이며 설치 완료나 실제 ABI 호환 검증 결과가 아니다. [계산 영수증](../../build/diagnostics/termux-omarchy-full-transaction-options-20261009-01/receipt.json), [전체 후보 및 모든 의존성](../../build/diagnostics/termux-omarchy-full-transaction-options-20261009-01/full.json).

패키지 설치·제거·다운로드, ADB 접근, 사용자 홈·설정·프로필 변경은 하지 않았다. 원본 592개 inventory와 고정 DB, 기존 resolver 소스는 수정하지 않았다. `pacman -Syu`를 포함한 전체 시스템 업그레이드는 이 후보의 실행 방법이 아니다.

## 고정 기준과 검증 방법

기준은 [실기기 inventory](../../build/diagnostics/termux-omarchy-full-package-metadata-device-20261009-02/installed-inventory.json)의 592개와 고정 원본 소스 `81145eb1fd41532fcae4310b26f860608e2eaf82`의 요청 158개다. 기준 목록 SHA256은 `2d33532c98c71ac342d77f240f9fcdfdcea360a6b86832334c74facf027c8e97`, `depends`를 포함한 metadata SHA256은 `54d8051ae0bb8918a36674c4168f885edc8f6662609c8475deb6f2fb6d5328a4`다. [기존 대조](2026-10-09-omarchy-termux-full-coverage.md)의 **52/158 충족·106개 미충족**, 추가 전용 336개와 차단 항목 5개를 재현했다.

계산은 기존 inventory에서 아래 다섯 이름만 제외한 **별도의 계산용 집합**을 만든 뒤, 새 버전 네 개를 정확한 버전으로 요청하고 기존 resolver에 전달했다. 원본 inventory에서 항목을 지우거나 수정하지 않았다. 이어 설치 후 예상 집합 전체를 별도 검증하여, 남겨 두는 기존 패키지의 `depends`도 `provides`·버전 제약·충돌과 함께 검사했다. 기존 resolver 자체는 설치된 패키지의 역의존성을 검사하지 않으므로 이 두 번째 검증이 필요하다. [재현 스크립트](../../build/diagnostics/termux-omarchy-full-transaction-options-20261009-01/reproduce.py), [입력 파일 경로·바이트·SHA](../../build/diagnostics/termux-omarchy-full-transaction-options-20261009-01/source-refs.json).

고정 원본 libalpm 비교기를 사용했고 실기기 version comparison 3개와 일치했다. `gvfs=1.60.3` 요구는 libalpm에서 `1.60.3-3`과 일치한다. 기존 592개의 의존성 3,132개와 최종 예상 927개의 의존성 5,092개를 검사했으며, 두 집합 모두 선언된 의존성 누락 0·충돌 0이었다. 불량 metadata로 기존부터 격리한 `findnewest`와 `texlive-doc` 2개는 계속 제외했고 이 후보가 요청하지 않는다. [전체 역의존성 검증](../../build/diagnostics/termux-omarchy-full-transaction-options-20261009-01/reverse-dependency-audit.json).

## 필요한 기존 패키지 변경

| 변경 대상 | 현재 → 후보 | 고정 DB가 요구하는 이유 | 다운로드 bytes |
| --- | --- | --- | ---: |
| `gst-plugins-bad-libs` | `1.28.6-3` → `1.28.7-2` | `sushi → gst-plugin-gtk`의 정확한 버전 요구 | 2,718,856 |
| `gst-plugins-base-libs` | `1.28.6-3` → `1.28.7-2` | 같은 경로와 `kdenlive → frei0r-plugins → opencv → gst-plugins-base` | 2,277,568 |
| `gstreamer` | `1.28.6-3` → `1.28.7-2` | 새 GST 라이브러리·plugin의 정확한 버전 요구 | 1,983,072 |
| `gvfs` | `1.60.2-4` → `1.60.3-3` | `gvfs-mtp`, `gvfs-nfs`, `gvfs-smb`가 `gvfs=1.60.3` 요구 | 895,944 |
| `ttf-jetbrains-mono-nerd` → `ttf-jetbrains-mono-nerd-basic` | full `3.5.1-2` 제거 → basic `3.5.1-1` 추가 | 원본이 basic을 요청하며 basic은 기존 full과 충돌 | 5,555,726 |

이는 같은 다섯 이름으로 한정한 **고정 DB 내 최소 예외 집합**이다. 각 예외를 하나씩 철회한 계산에서 그 패키지의 원래 차단 항목이 다시 나타났다. 다른 역사적 저장소의 구버전 아카이브 조합까지 탐색한 전역 최소 해라는 뜻은 아니다. [예외별 필요성 증거](../../build/diagnostics/termux-omarchy-full-transaction-options-20261009-01/reverse-dependency-audit.json).

GST 세 패키지는 함께 업데이트해야 한다. 기존 `gst-plugins-bad-libs`가 기존 base-libs와 gstreamer의 정확한 버전을, 기존 base-libs가 기존 gstreamer의 정확한 버전을 요구하기 때문이다. 세 패키지를 함께 바꾸면 이 내부 요구도 모두 `1.28.7-2`로 바뀐다. 그 밖의 설치된 소비자인 `gtk4`, `evince`, `gupnp-dlna`, `localsearch`, `nautilus`, `xdg-desktop-portal`의 선언된 요구는 새 버전으로 충족되며 이 소비자들의 버전은 변경하지 않는다. `gvfs`의 설치된 소비자인 `evince`와 `nautilus`도 유지한다. 실제 로딩·미디어 재생·파일 미리보기의 회귀 검사는 별도다.

full 폰트에 대한 설치된 패키지 역의존성은 없다. basic은 `ttf-font-nerd`와 `ttf-jetbrains-mono-nerd=3.5.1`을 제공한다. 반대로 기존 full은 `ttf-jetbrains-mono-nerd-basic`을 제공하지 않으므로 full을 그대로 둔 상태를 원본 basic 요청 충족으로 바꿔 계산하지 않았다. 원본 [Alacritty 설정](../../build/omarchy-sources/omarchy/config/alacritty/alacritty.toml)과 [fontconfig 기본값](../../build/omarchy-sources/omarchy/default/fontconfig/conf.avail/50-omarchy.conf)은 `JetBrainsMono Nerd Font`를 참조한다. 실제 basic 아카이브의 family·style·아이콘 범위와 개인 설정에 선택된 폰트의 표시 동등성은 아직 확인하지 않았다. 폰트 이름을 맞추려고 개인 설정을 덮어쓰는 작업은 이 후보에 포함하지 않는다.

## 후보와 실행 단위

| 후보 | 아카이브 | 기존 업데이트 / 제거 | 새 이름 | 다운로드 bytes | 예상 총 설치 수 / 원본 충족 |
| --- | ---: | --- | ---: | ---: | --- |
| [전체를 한 번에 계산](../../build/diagnostics/termux-omarchy-full-transaction-options-20261009-01/full.json) | 340 | 4 / 1 | 336 | 1,260,171,927 | 927 / 158개 |
| [차단 해소 선행 묶음](../../build/diagnostics/termux-omarchy-full-transaction-options-20261009-01/blocker-batch.json) | 5 | 4 / 1 | 1 | 13,431,166 | 592 / 53개 |
| [선행 묶음 이후 추가 전용](../../build/diagnostics/termux-omarchy-full-transaction-options-20261009-01/after-blocker-batch.json) | 335 | 0 / 0 | 335 | 1,246,740,761 | 927 / 158개 |

**권장 실행 단위는 작은 차단 해소 묶음을 먼저 검증하고, 새 실기기 inventory로 나머지를 다시 고정하는 방식이다.** 선행 묶음은 위 표의 다섯 아카이브만 필요하며 추가 의존성은 없다. 그 뒤 335개 추가 전용 후보와 340개 전체 후보의 최종 이름·버전·`depends`·`provides`·`conflicts` 집합은 정확히 일치한다. 전체 예상 Q SHA256은 `2fab79b893efa5c9a7ad445d0fb729620a10144e28819cc03d04c86b4c3168e5`이며, 이는 실제 설치 결과 해시가 아니다. [전체 예상 inventory](../../build/diagnostics/termux-omarchy-full-transaction-options-20261009-01/full-projected-inventory.json).

회귀 범위를 더 줄이려면 선행 묶음도 [GST family 3개, 6,979,496 bytes](../../build/diagnostics/termux-omarchy-full-transaction-options-20261009-01/gstreamer-family.json), [GVfs 1개, 895,944 bytes](../../build/diagnostics/termux-omarchy-full-transaction-options-20261009-01/gvfs.json), [폰트 교체 1개, 5,555,726 bytes](../../build/diagnostics/termux-omarchy-full-transaction-options-20261009-01/font-replacement.json)로 나눌 수 있다. 이 세 파일은 각각 원래 592개 기준의 독립 후보이므로, 순서대로 실행할 때는 매번 새 기준 목록으로 다시 계산해야 한다. GST family 내부의 세 업데이트를 따로 실행하는 계획은 제안하지 않는다.

전체 후보의 아카이브 metadata상 `ISIZE` 합은 4,994,734,930 bytes다. 그중 새 이름 336개의 합은 4,941,896,570 bytes다. 기존 네 패키지의 이전 실제 설치 크기가 이번 inventory에 없으므로 이 수치는 디스크 사용량의 순증가량이 아니다.

Neovim helper 7개는 이 336개 안에 포함되며, 8,042,272 bytes의 로컬 아카이브가 전체 후보 SHA와 일치한다. [실기기 서명 영수증](../../build/diagnostics/termux-omarchy-nvim-tools-signatures-device-20261009-01/receipt.json)은 기존 592개 목록과 서명 7개 검증을 확인하며 `packageWrites=false`, 7개 모두 `missing`으로 기록한다. 이 기준에서는 설치 완료로 세지 않는다. 다른 로컬 캐시를 가정하지 않을 때 전체 후보 중 아직 확보하지 않은 아카이브는 1,252,129,655 bytes다. 이후 실제 설치 목록이 바뀌면 이 592개 후보를 그대로 실행하지 않고 재계산한다.

## 아카이브 준비와 설치 구현에 남은 경계

의존성 해소와 서명된 설치 준비는 별개다. 340개 중 309개에는 고정 DB의 `PGPSIG`가 있고, Omarchy 저장소의 31개에는 없다. **PGPSIG 부재는 아카이브 자체가 서명되지 않았다는 판정이 아니다.** 해당 detached signature를 별도로 확보하여 기존 trusted keyring으로 검증해야 한다. basic 폰트도 이 31개에 속하므로 작은 선행 묶음조차 현재 파일만으로 trusted transaction 완료를 주장할 수 없다. 전체 목록은 [full.json의 `missingRepositoryPGPSIG`](../../build/diagnostics/termux-omarchy-full-transaction-options-20261009-01/full.json)에 보존했다. 신뢰 설정을 낮추거나 키를 자동 승인하는 대안은 후보에 없다.

다음 구현은 원본 Q/metadata SHA, 정확한 네 업데이트와 한 폰트 교체, 새 패키지 allowlist를 고정한 별도 transaction으로 진행할 수 있다. 기존 tools·IME·Neovim 추가 전용 설치기는 동일 이름의 버전 차이를 거절하므로 그 pins·journal을 바꿔 재사용하지 않는다. 각 후보 JSON에는 다운로드 URL·filename·SHA256·크기·버전·전체 직접 의존성과 제공 항목이 모두 들어 있다.

실제 아카이브 확보 단계에서는 SHA·서명·`.PKGINFO`와 파일 목록, `.INSTALL` 및 관련 pacman hook의 변경 범위를 확인해야 한다. 특히 사용자 소유 Neovim 설정·plugin, 폰트 설정과 홈 파일을 쓰는 package/scriptlet은 이 후보의 허용 범위에 넣지 않는다. 폰트 충돌은 명시한 교체 하나만 같은 검증된 transaction 안에서 처리하고, 선행 `pacman -R`이나 포괄적인 overwrite·dependency 우회로 풀지 않는다. 아직 실제 pacman의 로컬 transaction 준비·파일 충돌 검사도 실행하지 않았다.

실행 전에는 private PRoot guard와 소유권이 확인된 종료 상태를 재검증하고, 실기기 `pacman -Q`가 그 transaction의 고정 기준과 같은지 확인해야 한다. 네 업데이트 외 기존 버전 변경, full 폰트 외 제거, allowlist 밖 추가가 계획에 나타나면 중단한다. 실행 후에는 동일 allowlist와 보존된 587개의 버전, pacman 설정·sync DB·개인 설정 보존을 확인한다. 현재 실행되는 Quickshell bar/menu와 GTK 파일 앱·미디어 동작은 GST/GVfs 변경 전후의 회귀 확인 대상이다.

원본 요청 158/158이 metadata상 충족돼도 Android에서 systemd·Bluetooth·전원·Docker 등 서비스가 작동한다는 뜻은 아니다. 원본 소스·매뉴얼·QML 적용과 개인 Neovim 구성 역시 이 transaction과 별도 범위다. 이 문서의 모든 후보는 `readyToInstall=false`이며, 이유는 위 서명·실제 transaction·실행 회귀 검증이 아직 남아 있기 때문이다.
