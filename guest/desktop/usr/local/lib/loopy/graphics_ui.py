#!/usr/bin/python3
"""Actionable graphics alternatives in the existing Linux terminal."""
import json
import os
import subprocess
from graphics_session import read_report, selected_provider

PATHS = '''
GPU 경로                         현재 조건 / 다음 방법
Android GLES 출력                앱의 권한/진단 화면에서 현재 출력 상태 확인
CPU OpenGL: llvmpipe → softpipe   실제 픽셀 검사 후 자동 선택, 실패하면 기본 Cairo
VirGL / virpipe                  APK 서버·Mesa probe 포함, 픽셀 통과 시 선택 검사
Venus                            Vulkan 외부 메모리/동기화 및 vtest bridge 필요
Zink + Turnip / Freedreno KGSL    지원 Adreno, 드라이버, 장치 접근 및 렌더 검사 필요
Panfrost / PanVK / Lima           지원 Mali 및 호환 DRM kernel/device 접근 필요
Android EGL / Vulkan + ABI bridge OEM 드라이버와 guest ABI 연동/출력 구현 필요
Termux:X11 + VirGL/Turnip         별도 앱/환경 설치 및 해당 기기 설정 필요
root chroot / custom kernel      별도 관리 환경에서 GPU 접근과 드라이버 구성 필요
원격 Linux GPU                   GPU PC에 접속: 브라우저 또는 터미널 SSH 사용
Android 네이티브 앱               데스크톱 메뉴의 Android 앱/브라우저로 이동

현재 데스크톱은 pixman/wl_shm 출력을 유지합니다. OpenGL offscreen 성공은
GUI 전달이나 GPU 하드웨어 가속의 합격 증거가 아닙니다.
'''


def main():
    token = os.environ.get('LOOPY_SESSION', '')
    report = read_report(token)
    selected = selected_provider(report, token)
    print('Loopy Desktop · GPU 대체 방법\n현재 검증된 GL 경로: ' + selected)
    for provider in report.get('providers', []):
        print('  ' + provider.get('id', '?') + ': ' + provider.get('status', '?')
              + ' · ' + provider.get('reason', '')[:180])
    print(PATHS)
    while True:
        print('\n1 CPU OpenGL 창 검사 · 2 다시 검사 · 3 Android 설정 · 4 Android 브라우저 · 5 VirGL 창 검사 · Enter 닫기')
        try: choice = input('선택: ').strip()
        except EOFError: return
        if not choice: return
        if choice == '1':
            if selected == 'cairo': print('검증된 GL 경로가 없습니다. 기본 데스크톱을 계속 사용할 수 있습니다.')
            else: subprocess.run(['/usr/local/bin/loopy-gl', '/usr/bin/python3',
                                  '/usr/local/lib/loopy/graphics_demo.py'])
        elif choice == '2':
            from graphics_probe import collect
            fresh = collect(virgl_socket=report.get('virglSocket'))
            print(json.dumps(fresh, ensure_ascii=False, indent=2))
            print('검사 결과는 현재 앱을 재시작하지 않습니다. 다음 데스크톱 세션에서 다시 검사합니다.')
        elif choice in ('3', '4'):
            from desktop_ui import write_request, IPC
            write_request(IPC, token, 'settings' if choice == '3' else 'browser')
            return
        elif choice == '5':
            print('VirGL 검사는 한 앱씩 실행합니다. 실기기 GPU 여부와 창 전달은 별도 확인이 필요합니다.')
            subprocess.run(['/usr/local/bin/loopy-gl', '--virgl', '/usr/bin/python3',
                            '/usr/local/lib/loopy/graphics_demo.py'])


if __name__ == '__main__': main()
