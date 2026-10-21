"""Bounded type-only producer diagnostics; compositor state is not app ACK."""
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time

MAX_BYTES, MAX_JOBS, MAX_TIMELINE = 16384, 16, 16


def state(value):
    if value is None: return None
    surrounding = value.surrounding
    return {'active': value.active, 'pending_active': value.pending_active,
            'transition': value.transition, 'epoch': value.epoch, 'serial': value.serial,
            'surrounding_bytes': len(surrounding[0]) if surrounding else None,
            'cursor': surrounding[1] if surrounding else None,
            'anchor': surrounding[2] if surrounding else None, 'purpose': value.purpose}


class Ledger:
    def __init__(self, directory, token):
        if not re.fullmatch(r'[A-Za-z0-9-]{1,64}', token): raise ValueError('Invalid input trace token')
        self.directory, self.token = Path(directory), token
        self.history, self.sequence, self.write_failures = [], 0, 0

    def job(self, session, text, backspaces, key):
        self.sequence += 1
        return Job(self, session, {'sequence': self.sequence, 'utf8_bytes': len(text.encode()),
            'codepoints': len(text), 'backspaces': backspaces, 'key_present': key is not None,
            'backend': 'unselected', 'reason': 'unselected', 'counts': {}, 'timeline': [], 'timeline_omitted': 0})

    def save(self, record):
        self.history.append(record); self.history = self.history[-MAX_JOBS:]
        temporary = None
        try:
            info = self.directory.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
                raise ValueError('Input trace directory is not owned')
            while True:
                data = (json.dumps({'schema': 1, 'token': self.token, 'write_failures': self.write_failures,
                    'jobs': self.history}, separators=(',', ':')) + '\n').encode()
                if len(data) <= MAX_BYTES: break
                row = next((row for row in self.history if row['timeline']), None)
                if row is not None:
                    row['timeline'].pop(0); row['timeline_omitted'] += 1
                else: self.history.pop(0)
            fd, temporary = tempfile.mkstemp(prefix='input-trace-' + self.token + '-', suffix='.new', dir=self.directory)
            with os.fdopen(fd, 'wb') as target: target.write(data)
            os.replace(temporary, self.directory / ('input-trace-' + self.token + '.json'))
        except (OSError, ValueError, TypeError):
            self.write_failures += 1  # Diagnostics must not change input success/failure.
        finally:
            if temporary is not None:
                try: os.unlink(temporary)
                except OSError: pass


class Job:
    def __init__(self, ledger, session, record):
        self.ledger, self.session, self.record = ledger, session, record
        self.started, self.last_state = time.monotonic(), None

    def __enter__(self): return self

    def selected(self, backend, reason, current):
        self.record.update(backend=backend, reason=reason, initial=state(current))
        self.note('selected', current)

    def note(self, kind, current, **values):
        self.last_state = state(current)
        counts = self.record['counts']
        count = 'im_done' if kind == 'im-event' and values.get('opcode') == 5 else kind.replace('-', '_')
        counts[count] = counts.get(count, 0) + values.get('pairs', 1)
        event = dict(self.last_state or {}); event.update(kind=kind, **values)
        timeline = self.record['timeline']
        if len(timeline) >= MAX_TIMELINE:
            timeline.pop(0); self.record['timeline_omitted'] += 1
        timeline.append(event)

    def __exit__(self, kind, error, traceback):
        wire = self.session.wire
        self.record.update(result=kind.__name__ if kind else 'ok',
            elapsed_ms=int((time.monotonic() - self.started) * 1000), wire_closed=wire is None,
            final=state(wire.ime) if wire is not None else self.last_state)
        self.ledger.save(self.record)
        return False
