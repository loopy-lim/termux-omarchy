#!/usr/bin/env python3
"""Collect read-only Android shell evidence for a desktop feasibility audit."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
SERIAL_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")
WINDOW_LINE = re.compile(
    r"^\s*(?:mGlobalConfiguration|mOverrideConfiguration|overrideConfig|"
    r"mSupportsFreeform|mForceDesktopMode|mDisplayRotation|"
    r"mInitialDisplayWidth|mInitialDisplayHeight|mBaseDisplayWidth|"
    r"mBaseDisplayHeight|mDisplayWindowingMode|mPreferredDisplayModeId|"
    r"mPreferredDesktopMode|mDesktopMode|mSupportsDesktopMode|"
    r"mIsDesktopModeSupported)\s*[=:]"
)
INPUT_LINE = re.compile(
    r"^\s*(?:\d+: .*|Device \d+: .*|BuiltInKeyboardId: .*|"
    r"Classes: .*|Path: /dev/input/.*|Sources: .*|KeyboardType: .*|"
    r"IsExternal: .*|IsVirtualDevice: .*|DeviceType: .*|"
    r"Touch Input Mapper .*|Motion Ranges:|[XY]: min=.*)\s*$"
)
PROPERTIES = {
    "manufacturer": "ro.product.manufacturer",
    "model": "ro.product.model",
    "device": "ro.product.device",
    "build_fingerprint": "ro.build.fingerprint",
    "android_release": "ro.build.version.release",
    "android_sdk": "ro.build.version.sdk",
    "security_patch": "ro.build.version.security_patch",
    "primary_abi": "ro.product.cpu.abi",
    "abi_list": "ro.product.cpu.abilist",
    "boot_completed": "sys.boot_completed",
    "board_platform": "ro.board.platform",
    "hardware": "ro.hardware",
    "build_type": "ro.build.type",
    "emulator": "ro.kernel.qemu",
    "verified_boot_state": "ro.boot.verifiedbootstate",
    "bootloader_locked": "ro.boot.flash.locked",
    "vbmeta_device_state": "ro.boot.vbmeta.device_state",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Android 데스크톱 가능성 조사를 위한 읽기 전용 ADB 진단 자료 수집"
    )
    parser.add_argument("--serial", required=True, help="조사할 ADB 기기의 정확한 serial (필수)")
    parser.add_argument("--adb", type=Path, help="ADB 실행 파일 경로 (기본: PATH, Android SDK)")
    parser.add_argument("--output", type=Path, help="새 결과 디렉터리 (기본: docs/validation/<KST 시각>-<serial>)")
    parser.add_argument(
        "--expect-manufacturer",
        help="제조사가 일치할 때만 전체 자료 수집 (예: lenovo)",
    )
    parser.add_argument("--expect-model", help="모델이 일치할 때만 전체 수집 (예: TB522FU; Lenovo 접두사 허용)")
    args = parser.parse_args()
    if not SERIAL_PATTERN.fullmatch(args.serial):
        parser.error("--serial은 영숫자로 시작하고 영숫자, 점, 밑줄, 콜론, 하이픈만 포함해야 합니다")
    return args


def find_adb(explicit: Path | None) -> str:
    if explicit is not None:
        path = explicit.expanduser().resolve()
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError(f"ADB 실행 파일을 사용할 수 없습니다: {path}")
        return str(path)
    found = shutil.which("adb")
    if found:
        return found
    sdk = Path.home() / "Library/Android/sdk/platform-tools/adb"
    if sdk.is_file() and os.access(sdk, os.X_OK):
        return str(sdk)
    raise ValueError("ADB를 찾지 못했습니다. --adb로 실행 파일 경로를 지정하세요")


def invoke(adb: str, serial: str, command: list[str], timeout: int = 12) -> dict:
    started = time.monotonic()
    try:
        process = subprocess.run(
            [adb, "-s", serial, *command],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return {
            "stdout": process.stdout,
            "stderr": process.stderr,
            "exit_code": process.returncode,
            "timed_out": False,
            "duration_seconds": round(time.monotonic() - started, 3),
        }
    except subprocess.TimeoutExpired as error:
        def decoded(value: bytes | str | None) -> str:
            if value is None:
                return ""
            return value.decode("utf-8", "replace") if isinstance(value, bytes) else value

        return {
            "stdout": decoded(error.stdout),
            "stderr": decoded(error.stderr),
            "exit_code": None,
            "timed_out": True,
            "duration_seconds": round(time.monotonic() - started, 3),
        }


def succeeded(result: dict) -> bool:
    return result["exit_code"] == 0 and not result["timed_out"]


def transport_failed(result: dict) -> bool:
    return not succeeded(result) and bool(re.search(
        r"device (?:'.*?' )?(?:not found|offline)|no devices/emulators",
        result["stderr"],
        re.IGNORECASE,
    ))


def probe(adb: str, serial: str, *shell_args: str, timeout: int = 12) -> dict:
    return invoke(adb, serial, ["shell", *shell_args], timeout)


def read_identity(adb: str, serial: str) -> dict[str, dict]:
    identity = {}
    for label in ("manufacturer", "model"):
        identity[label] = probe(adb, serial, "getprop", PROPERTIES[label])
    return identity


def canonical_model(value: str) -> str:
    return re.sub(r"^lenovo\s+", "", value.strip().casefold())


def commands() -> list[tuple[str, list[str], int]]:
    access_script = (
        'for p in /dev/input /dev/input/event* /dev/uinput '
        '/dev/kgsl-3d0 /dev/dri /dev/dri/renderD* /sys/class/drm '
        '/sys/fs/cgroup /proc/self/ns /proc/self/ns/*; do '
        '[ -e "$p" ] || continue; '
        'ls -ld "$p"; '
        'if [ -r "$p" ]; then r=yes; else r=no; fi; '
        'if [ -w "$p" ]; then w=yes; else w=no; fi; '
        'printf "DAC shell access: %s read=%s write=%s\\n" "$p" "$r" "$w"; '
        'done'
    )
    return [
        ("uname", ["uname", "-a"], 12),
        ("shell_identity", ["id"], 12),
        ("selinux", ["getenforce"], 12),
        ("input_capabilities", ["getevent", "-lp"], 10),
        ("input_service", ["dumpsys", "input"], 20),
        ("features", ["pm", "list", "features"], 20),
        ("display_size", ["wm", "size"], 12),
        ("display_density", ["wm", "density"], 12),
        ("window_configuration", ["dumpsys", "window"], 20),
        ("multiwindow_support", ["am", "supports-multiwindow"], 12),
        ("display_windowing_mode", ["cmd", "window", "get-display-windowing-mode"], 12),
        ("multiwindow_resource", ["cmd", "overlay", "lookup", "android", "android:bool/config_supportsMultiWindow"], 12),
        ("desktop_resource", ["cmd", "overlay", "lookup", "android", "android:bool/config_isDesktopModeSupported"], 12),
        ("freeform_setting", ["settings", "get", "global", "enable_freeform_support"], 12),
        ("external_desktop_setting", ["settings", "get", "global", "force_desktop_mode_on_external_displays"], 12),
        ("interface_modes", ["sh -c " + shlex.quote(access_script)], 12),
        ("su_presence", ["sh -c 'command -v su'"], 12),
        ("cgroup_mounts", ["cat", "/proc/mounts"], 12),
        ("window_commands", ["cmd", "window", "help"], 12),
        ("activity_commands", ["am", "help"], 12),
    ]


def sanitize(label: str, output: str) -> str:
    if label == "input_service":
        # dumpsys input includes recent and current events; retain capability lines only.
        return "\n".join(line.strip() for line in output.splitlines() if INPUT_LINE.fullmatch(line)) + "\n"
    if label == "window_configuration":
        return "\n".join(line.strip() for line in output.splitlines() if WINDOW_LINE.search(line)) + "\n"
    if label == "cgroup_mounts":
        return "\n".join(line for line in output.splitlines() if "cgroup" in line) + "\n"
    return output


def save_result(directory: Path, label: str, result: dict) -> dict:
    (directory / f"{label}.stdout.txt").write_text(
        sanitize(label, result["stdout"]), encoding="utf-8"
    )
    (directory / f"{label}.stderr.txt").write_text(result["stderr"], encoding="utf-8")
    return {
        "stdout_file": f"{label}.stdout.txt",
        "stderr_file": f"{label}.stderr.txt",
        "exit_code": result["exit_code"],
        "timed_out": result["timed_out"],
        "duration_seconds": result["duration_seconds"],
    }


def main() -> int:
    args = parse_args()
    try:
        adb = find_adb(args.adb)
    except ValueError as error:
        print(f"오류: {error}", file=sys.stderr)
        return 2

    state = invoke(adb, args.serial, ["get-state"], 8)
    if not succeeded(state) or state["stdout"].strip() != "device":
        print(f"오류: {args.serial} 연결 상태가 device가 아닙니다: "
              f"{state['stdout'].strip() or state['stderr'].strip() or '응답 없음'}", file=sys.stderr)
        return 2

    identity = read_identity(adb, args.serial)
    if any(not succeeded(item) or not item["stdout"].strip() for item in identity.values()):
        print("오류: 제조사/모델을 읽지 못해 조사를 시작하지 않았습니다", file=sys.stderr)
        return 2
    manufacturer = identity["manufacturer"]["stdout"].strip()
    model = identity["model"]["stdout"].strip()
    if args.expect_manufacturer and manufacturer.casefold() != args.expect_manufacturer.casefold():
        print(f"오류: 제조사 불일치: 예상 {args.expect_manufacturer}, 실제 {manufacturer} ({model})", file=sys.stderr)
        return 2
    if args.expect_model and canonical_model(model) != canonical_model(args.expect_model):
        print(f"오류: 모델 불일치: 예상 {args.expect_model}, 실제 {model}", file=sys.stderr)
        return 2

    collected_at_utc = dt.datetime.now(dt.timezone.utc)
    collected_at_kst = collected_at_utc.astimezone(ZoneInfo("Asia/Seoul"))
    timestamp = collected_at_kst.strftime("%Y%m%dT%H%M%S%z")
    output = args.output or ROOT / "docs/validation" / f"{timestamp}-{args.serial}"
    output = output.expanduser().resolve()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        print(f"오류: 새 결과 디렉터리를 만들 수 없습니다: {error}", file=sys.stderr)
        return 2

    receipt = {
        "schema_version": 1,
        "collected_at_utc": collected_at_utc.isoformat(),
        "collected_at_kst": collected_at_kst.isoformat(),
        "serial": args.serial,
        "adb": adb,
        "collection_context": "adb shell; shell DAC checks are not normal app permissions",
        "manufacturer": manufacturer,
        "model": model,
        "status": "complete",
        "probes": {},
    }
    receipt["probes"]["connection_state_before"] = save_result(output, "connection_state_before", state)
    for label, result in identity.items():
        receipt["probes"][f"property_{label}"] = save_result(output, f"property_{label}", result)

    transport_lost = False
    for label, property_name in PROPERTIES.items():
        if label in identity:
            continue
        result = probe(adb, args.serial, "getprop", property_name)
        receipt["probes"][f"property_{label}"] = save_result(output, f"property_{label}", result)
        if transport_failed(result):
            transport_lost = True
            break

    if not transport_lost:
        for label, command, timeout in commands():
            result = probe(adb, args.serial, *command, timeout=timeout)
            receipt["probes"][label] = save_result(output, label, result)
            if transport_failed(result):
                transport_lost = True
                break

    if not transport_lost:
        final_state = invoke(adb, args.serial, ["get-state"], 8)
        receipt["probes"]["connection_state_after"] = save_result(
            output, "connection_state_after", final_state
        )
        transport_lost = not succeeded(final_state) or final_state["stdout"].strip() != "device"

    if transport_lost:
        receipt["status"] = "incomplete_transport_lost"
    (output / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = "수집 완료 (기능 검증 아님)" if not transport_lost else "수집 미완료 (연결 중단)"
    print(f"{summary}: {manufacturer} {model} ({args.serial})\n결과: {output}")
    print("주의: 결과는 adb shell 관찰이며 일반 앱 권한이나 기능 동작을 증명하지 않습니다")
    return 1 if transport_lost else 0


if __name__ == "__main__":
    sys.exit(main())
