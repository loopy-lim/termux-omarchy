"""Bounded public-fixture timing protocol. Never accepts key values or coordinates."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import stat
import uuid

LIMIT = 2048
KINDS = ('key_down', 'key_up', 'button_down', 'button_up', 'motion')
IDENTITY = ('nonce', 'session', 'uid', 'pid', 'birth', 'sid')


def require(value):
    if not value: raise ValueError('latency-fixture-boundary')


def integer(value, minimum=0, maximum=(1 << 63) - 1):
    require(type(value) is int and minimum <= value <= maximum)
    return value


def checked_identity(value):
    require(type(value) is dict and set(value) == set(IDENTITY))
    require(isinstance(value['nonce'], str) and re.fullmatch('[0-9a-f]{32}', value['nonce']))
    require(isinstance(value['session'], str) and str(uuid.UUID(value['session'])) == value['session'])
    for key in ('uid', 'pid', 'birth', 'sid'):
        integer(value[key], 0 if key == 'uid' else 1)
    return dict(value)


def own_identity(nonce, session):
    """Native /proc UID stays separate from PRoot's simulated getuid()."""
    before = Path('/proc/self/stat').read_bytes()
    require(0 < len(before) < 4096)
    fields = before[before.rfind(b')') + 2:].split()
    require(len(fields) >= 20)
    status = Path('/proc/self/status').read_bytes()
    require(len(status) < 16384)
    matches = re.findall(rb'^Uid:\s+([0-9]+)\s+', status, re.M)
    after = Path('/proc/self/stat').read_bytes()
    require(0 < len(after) < 4096)
    next_fields = after[after.rfind(b')') + 2:].split()
    require(len(matches) == 1 and len(next_fields) >= 20
            and before.split(b' ', 1)[0] == after.split(b' ', 1)[0] == str(os.getpid()).encode()
            and fields[19] == next_fields[19])
    return checked_identity(dict(nonce=nonce, session=session, uid=int(matches[0]),
                                 pid=os.getpid(), birth=int(fields[19]), sid=os.getsid(0)))


def stats(values):
    require(len(values) <= LIMIT)
    require(all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in values))
    ordered = sorted(values)
    if not ordered: return dict(count=0, p50_ms=None, p95_ms=None, max_ms=None)
    def at(q): return round(ordered[max(0, math.ceil(len(ordered) * q) - 1)], 6)
    return dict(count=len(ordered), p50_ms=at(.5), p95_ms=at(.95), max_ms=round(ordered[-1], 6))


class Collector:
    def __init__(self, identity):
        self.identity = checked_identity(identity)
        self.ready = self.done = None
        self.events, self.painted = {}, set()
        self.samples = {kind: dict(arrival_gap_ms=[], source_gap_ms=[], event_to_callback_ms=[])
                        for kind in KINDS}
        self.previous, self.paint_callbacks = {}, 0
        self.last_arrival = self.last_complete = 0

    def receive(self, row):
        require(type(row) is dict and isinstance(row.get('type'), str) and self.done is None)
        kind = row['type']
        if kind == 'READY':
            require(self.ready is None and set(row) == {'type', 'schema', 'backend', 'width', 'height',
                                                        'window', *IDENTITY})
            require(row['schema'] == 1 and type(row['schema']) is int)
            require(checked_identity({k: row[k] for k in IDENTITY}) == self.identity)
            require(row['backend'] in ('x11-xsync', 'wayland-after-paint'))
            require(type(row['width']) is int and row['width'] == 640
                    and type(row['height']) is int and row['height'] == 420)
            if row['backend'] == 'x11-xsync': integer(row['window'], 1)
            else: require(row['window'] is None)
            self.ready = dict(row)
            return
        require(self.ready is not None)
        if kind == 'EVENT':
            require(set(row) == {'type', 'id', 'kind', 'arrival_ns', 'source_ms'})
            seq = integer(row['id'], 1, LIMIT)
            require(seq == len(self.events) + 1 and row['kind'] in KINDS)
            arrival, source = integer(row['arrival_ns'], 1), integer(row['source_ms'], 0, 0xffffffff)
            require(arrival >= self.last_arrival)
            previous = self.previous.get(row['kind'])
            if previous:
                delta = (source - previous['source_ms']) & 0xffffffff
                require(delta <= 120000)
                self.samples[row['kind']]['source_gap_ms'].append(float(delta))
                self.samples[row['kind']]['arrival_gap_ms'].append((arrival - previous['arrival_ns']) / 1e6)
            self.previous[row['kind']] = self.events[seq] = dict(row)
            self.last_arrival = arrival
        elif kind == 'PAINT':
            require(set(row) == {'type', 'ids', 'complete_ns'})
            require(type(row['ids']) is list and 0 < len(row['ids']) <= LIMIT)
            complete = integer(row['complete_ns'], 1)
            require(complete >= self.last_complete and len(set(row['ids'])) == len(row['ids']))
            for seq in row['ids']:
                integer(seq, 1, LIMIT)
                require(seq in self.events and seq not in self.painted
                        and complete >= self.events[seq]['arrival_ns'])
            for seq in row['ids']:
                event = self.events[seq]
                self.samples[event['kind']]['event_to_callback_ms'].append((complete - event['arrival_ns']) / 1e6)
                self.painted.add(seq)
            self.last_complete = complete
            self.paint_callbacks += 1
        elif kind == 'DONE':
            require(set(row) == {'type', 'reason', 'window_destroyed'})
            require(row['reason'] in ('deadline', 'event-limit', 'own-close'))
            require(type(row['window_destroyed']) is bool)
            self.done = dict(row)
        else: require(False)

    def result(self):
        require(self.ready is not None and self.done is not None)
        return dict(schema=1, identity=self.identity, backend=self.ready['backend'],
                    width=640, height=420, event_count=len(self.events),
                    paint_callbacks=self.paint_callbacks, unpainted_events=len(self.events) - len(self.painted),
                    callback_kind=('XSync-request-processed' if self.ready['backend'] == 'x11-xsync'
                                   else 'GdkFrameClock-after-paint'),
                    kinds={kind: {name: stats(values) for name, values in items.items()}
                           for kind, items in self.samples.items()},
                    physical_latency_measured=False, physical_fps_measured=False,
                    reason=self.done['reason'], window_destroyed=self.done['window_destroyed'])


def collect(path, identity):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1
                and stat.S_IMODE(before.st_mode) == 0o600 and before.st_size <= 2 * 1024 * 1024)
        obj = Collector(identity)
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            count = 0
            while line := stream.readline(65537):
                count += 1
                require(len(line) <= 65536 and line.endswith(b'\n') and count <= 2 * LIMIT + 2)
                obj.receive(json.loads(line))
        after = os.fstat(fd)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns))
        return obj.result()
    finally: os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    for key in IDENTITY:
        parser.add_argument('--' + key, type=str if key in ('nonce', 'session') else int, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(collect(args.capture, {k: getattr(args, k) for k in IDENTITY}), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        print('{"schema":1,"status":"failed","reason":"latency-fixture-boundary"}')
        return 1


if __name__ == '__main__': raise SystemExit(main())
