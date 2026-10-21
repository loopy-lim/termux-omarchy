"""Bounded startup decisions; no profile, title, URL, GTK or Android task access."""
import math
import os
import re
import subprocess

FAILURES = frozenset({'SUID_SANDBOX', 'USERNS_SANDBOX', 'ROOT_UNSUPPORTED'})
CHROMIUM = frozenset({'chromium', 'chromium-browser', 'google-chrome', 'google-chrome-stable',
                     'brave', 'brave-origin', 'microsoft-edge-stable'})


def plan(argv):
    if not isinstance(argv, (list, tuple)) or not 1 <= len(argv) <= 256:
        raise ValueError('Bounded browser argv required')
    total = 0
    for value in argv:
        if type(value) is not str or '\0' in value:
            raise ValueError('Literal browser arguments required')
        try:
            count = len(value.encode('utf-8'))
        except UnicodeError as error:
            raise ValueError('Valid browser Unicode required') from error
        if count > 8192:
            raise ValueError('Browser argument exceeds its bound')
        total += count + 1
    if not argv[0] or total > 65536:
        raise ValueError('Browser command exceeds its bound')
    result = list(argv)
    if os.path.basename(result[0]) in CHROMIUM:
        platforms = [value for value in result[1:] if value.startswith('--ozone-platform=')]
        if any(value != '--ozone-platform=wayland' for value in platforms):
            raise ValueError('This desktop requires the Wayland browser platform')
        if not platforms:
            result.insert(1, '--ozone-platform=wayland')
    return result


def spawn(argv, env=None):
    return subprocess.Popen(plan(argv), env=None if env is None else dict(env),
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, start_new_session=False)


class FatalClassifier:
    """Only fixed startup causes from the first 8KiB of this child's stderr."""
    def __init__(self):
        self.kind = None
        self.seen_bytes = 0
        self._pending = bytearray()

    def feed(self, data):
        if not isinstance(data, bytes):
            raise ValueError('Owned child stderr bytes required')
        selected = data[:max(0, 8192 - self.seen_bytes)]
        self.seen_bytes += len(selected)
        if self.kind is not None:
            return
        for value in selected:
            if self.kind is not None:
                break
            if value == 10:
                self._line()
            else:
                self._pending.append(value)
        if self.seen_bytes == 8192:
            self._line()

    def finish(self):
        if self.kind is None:
            self._line()

    def _line(self):
        data = bytes(self._pending).rstrip(b'\r'); self._pending.clear()
        if self.kind is not None:
            return
        fatal = re.match(rb'^(?:FATAL:|Check failed:|\[[0-9]+:[0-9]+:[0-9./]+:FATAL:[ -~]{1,160}\])', data)
        if fatal and b'SUID sandbox helper binary was found, but is not configured correctly' in data:
            self.kind = 'SUID_SANDBOX'
        elif fatal and b'No usable sandbox!' in data:
            self.kind = 'USERNS_SANDBOX'
        elif re.match(rb'^(?:\[[0-9]+:[0-9]+:[0-9./]+:ERROR:[ -~]{1,160}\] )?'
                      rb'Running as root without --no-sandbox is not supported\.', data):
            self.kind = 'ROOT_UNSUPPORTED'


class Startup:
    def __init__(self, pid, uid, birth, started, timeout=20):
        if (type(pid) is not int or not 0 < pid < 2**31 or type(uid) is not int or uid < 0
                or type(birth) is not int or birth < 1 or not _number(started)
                or not _number(timeout) or not 0 < timeout <= 120):
            raise ValueError('Owned browser identity and bounded deadline required')
        self.pid, self.uid, self.birth = pid, uid, birth
        self.started, self.timeout = started, timeout
        self.status = "PENDING"
        self.elapsed_ms = None

    def observe(self, now, exit_code, fatal, processes, clients,
                session_current=True, compositor_current=True):
        if self.status != 'PENDING':
            return self.status
        if not session_current or not compositor_current:
            self.status = 'SESSION_CHANGED'
        elif fatal in FAILURES:
            self.status = fatal
        elif exit_code is not None:
            self.status = 'EXITED'
        elif not self._leader(processes):
            self.status = 'PROCESS_CHANGED'
        elif not _number(now) or now < self.started:
            raise ValueError('One monotonic clock required')
        elif now - self.started >= self.timeout:
            self.status = 'TIMEOUT'
        elif self._window(processes, clients):
            self.status = 'READY'; self.elapsed_ms = (now - self.started) * 1000
        return self.status

    def _leader(self, processes):
        row = processes.get(self.pid) if isinstance(processes, dict) else None
        return (_process(row, self.pid, self.uid) and row['birth'] == self.birth)

    def _window(self, processes, clients):
        if not isinstance(clients, list) or len(clients) > 256:
            return False
        for row in clients:
            if (type(row) is dict and type(row.get('pid')) is int
                    and row.get('mapped') is True and row.get('hidden') is False
                    and row.get('xwayland') is False and self._descendant(row['pid'], processes)):
                return True
        return False

    def _descendant(self, pid, processes):
        seen = set()
        for _ in range(16):
            if pid in seen:
                return False
            seen.add(pid); row = processes.get(pid)
            if not _process(row, pid, self.uid) or row['birth'] < self.birth:
                return False
            if pid == self.pid:
                return row['birth'] == self.birth
            pid = row['ppid']
        return False


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _process(row, pid, uid):
    return (type(row) is dict and type(row.get('pid')) is int and row['pid'] == pid
            and type(row.get('uid')) is int and row['uid'] == uid
            and type(row.get('birth')) is int and row['birth'] > 0
            and type(row.get('ppid')) is int and row['ppid'] >= 0
            and row.get('state') in ('R', 'S', 'D', 'T', 't', 'W', 'I', 'P'))


def message(status, exit_code=None):
    messages = {
        'PENDING': '선택한 브라우저의 Wayland 창을 준비하는 중입니다.',
        'READY': '새 브라우저 프로세스의 Wayland 창이 준비됐습니다.',
        'SUID_SANDBOX': 'Chromium이 보안 샌드박스를 준비하지 못해 종료됐습니다. '
            '현재 Android Linux 환경에서는 필요한 root 소유 SUID helper를 사용할 수 없습니다.',
        'USERNS_SANDBOX': 'Chromium이 사용할 수 있는 보안 샌드박스를 찾지 못했습니다. '
            '현재 실행 환경에서 사용자 namespace 또는 실제 권한을 가진 helper가 필요합니다.',
        'ROOT_UNSUPPORTED': 'Chromium은 root 사용자로 보안 샌드박스를 켜고 실행할 수 없습니다.',
        'TIMEOUT': '브라우저의 새 Wayland 창을 아직 확인하지 못했습니다. '
            '실행 중인 브라우저는 종료하지 않았습니다. 열린 창을 확인해 주세요.',
        'SESSION_CHANGED': 'Linux 세션이 바뀌어 브라우저 시작 확인을 중단했습니다. 현재 세션에서 다시 열어 주세요.',
        'PROCESS_CHANGED': '브라우저 프로세스의 소유권을 확인하지 못해 시작 확인을 중단했습니다.',
        'UNAVAILABLE': '현재 Wayland 세션에서 브라우저 시작 확인을 준비하지 못했습니다.',
        'COMMAND_FAILED': '선택한 브라우저 명령을 실행하지 못했습니다. 기본 브라우저 설정을 확인하세요.',
    }
    if status == 'EXITED':
        code = str(exit_code) if type(exit_code) is int else '알 수 없음'
        return '브라우저 실행 요청이 종료됐습니다 (종료 코드 ' + code + '). 새 Wayland 창 준비는 확인하지 못했습니다.'
    return messages.get(status, messages['UNAVAILABLE'])
