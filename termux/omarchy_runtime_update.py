"""Apply reviewed stopped-runtime migrations, retaining every predecessor journal."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid

import omarchy_install as base
import omarchy_guest_install as installer
import omarchy_proot as proot_guard

OLD_RUNTIME_SHA = 'e88e8bb77998186009cab4c878f9a38a313bb9a7fe783ccf74f9ae5690b31935'
OLD_COMMANDS_SHA = '73d68426b2969d7f497e29d38f0c5394ab1c23befbe1865e17ae2cc3ea423f21'
INVENTORY_COMMANDS_SHA = '637e6cff516edb34af2f81133fc99d000d5f55b25a9b4595f1e792ba061c495e'
OLD_RESOURCES_SHA = '4e2999c012bdf756492d06931f8df50fbf42a8c99a2e0fe382638afc92fc0a57'
OLD_NAMES = ('omarchy.py', 'processes.py', 'omarchy_runtime.py', 'omarchy_resources.py',
             'omarchy_boot.py', 'omarchy_input.py', 'omarchy_audio.py', 'omarchy_android.py',
             'omarchy_android_client.py')
NEW_NAMES = ('omarchy_commands.py', 'omarchy_proot.py')
CHANGES = (*NEW_NAMES, 'omarchy_runtime.py', 'processes.py')
JOURNAL = 'runtime-update.json'
TMPDIR_JOURNAL = 'runtime-update-tmpdir.json'
INVENTORY_JOURNAL = 'runtime-update-inventory.json'
PROOT_TEMP_JOURNAL = 'runtime-update-proot-temp.json'
RESOURCES_JOURNAL = 'runtime-update-resources.json'
HEAL_JOURNAL = 'runtime-update-heal.json'
VIDEO_JOURNAL = 'runtime-update-video.json'
# Generation the heal migration installed (2026-10-20 deploy); the video migration's only predecessor.
HEAL_RUNTIME_SHA = {
    'omarchy_proot.py': 'afc958c73a4cdf9298b270f18639dcd298a9c46ce4fbe04250706b7d151ad19d',
    'omarchy_commands.py': '65d1782439d59e4e76c4d97754bfe22c5fd67e521bbf2208bc106fcaccc41d75',
    'omarchy.py': 'b55fc7245ebf71cd5a70b9291c29604c9834f9cd82aab70a908c4e28d29e5afe',
    'processes.py': 'cda6028651ccb08a55bacf91c68186e4e9189bf9456cfd79ca587f354d3c946e',
    'omarchy_runtime.py': '012b5037ab00d4e4dc8e28cf5874065cded7edefefa8bf1c1559e2b8b7da868a',
    'omarchy_resources.py': 'e3276fcdd7af97cdc7286d7f694cac5bf9eff2d7b87dda679f661ef52499fff3',
    'omarchy_boot.py': 'f7b10200f58f84922d1d993ace12e24c1f31e0d03f725c29871039c7ae0e3559',
    'omarchy_input.py': 'f9178533a1951dcf2da998cf477bd428dbfbeaeea92901aa76fef7fa13c59067',
    'omarchy_audio.py': 'eac4f59d05d203e86c34668f1393d0053e2a8888f6f994d539fca29c43a8b48d',
    'omarchy_android.py': '89fb4bb6cb2c76e0350ea460303479ac2d076834b80674d0adb357f7c0b34fad',
    'omarchy_android_client.py': '6b0e9308e2b88337309450b7d32a3bc2963dbd4fcfbaf50c1e82dace20cb3823',
}
VIDEO_SCOPE = frozenset(('omarchy_android.py', 'omarchy_android_client.py'))
DIRECT_JOURNAL = 'runtime-update-direct.json'
# Generation the video migration installed; the direct-fix migration's only predecessor.
VIDEO_RUNTIME_SHA = {
    'omarchy_proot.py': 'afc958c73a4cdf9298b270f18639dcd298a9c46ce4fbe04250706b7d151ad19d',
    'omarchy_commands.py': '65d1782439d59e4e76c4d97754bfe22c5fd67e521bbf2208bc106fcaccc41d75',
    'omarchy.py': 'b55fc7245ebf71cd5a70b9291c29604c9834f9cd82aab70a908c4e28d29e5afe',
    'processes.py': 'cda6028651ccb08a55bacf91c68186e4e9189bf9456cfd79ca587f354d3c946e',
    'omarchy_runtime.py': '012b5037ab00d4e4dc8e28cf5874065cded7edefefa8bf1c1559e2b8b7da868a',
    'omarchy_resources.py': 'e3276fcdd7af97cdc7286d7f694cac5bf9eff2d7b87dda679f661ef52499fff3',
    'omarchy_boot.py': 'f7b10200f58f84922d1d993ace12e24c1f31e0d03f725c29871039c7ae0e3559',
    'omarchy_input.py': 'f9178533a1951dcf2da998cf477bd428dbfbeaeea92901aa76fef7fa13c59067',
    'omarchy_audio.py': 'eac4f59d05d203e86c34668f1393d0053e2a8888f6f994d539fca29c43a8b48d',
    'omarchy_android.py': '12b2bab2b988b249cd41f707cea59ec116ea76bcad87aa731dd9fe64fb9930e4',
    'omarchy_android_client.py': 'e0daa3e8cb5114403641ee6e23087b41655c6ecf9365247f21d84313a0d17cd0',
}
DIRECT_SCOPE = frozenset(('omarchy_android.py',))
FREEZE_JOURNAL = 'runtime-update-freeze.json'
# Generation the direct migration installed; the freeze migration's only predecessor.
DIRECT_RUNTIME_SHA = {
    'omarchy_proot.py': 'afc958c73a4cdf9298b270f18639dcd298a9c46ce4fbe04250706b7d151ad19d',
    'omarchy_commands.py': '65d1782439d59e4e76c4d97754bfe22c5fd67e521bbf2208bc106fcaccc41d75',
    'omarchy.py': 'b55fc7245ebf71cd5a70b9291c29604c9834f9cd82aab70a908c4e28d29e5afe',
    'processes.py': 'cda6028651ccb08a55bacf91c68186e4e9189bf9456cfd79ca587f354d3c946e',
    'omarchy_runtime.py': '012b5037ab00d4e4dc8e28cf5874065cded7edefefa8bf1c1559e2b8b7da868a',
    'omarchy_resources.py': 'e3276fcdd7af97cdc7286d7f694cac5bf9eff2d7b87dda679f661ef52499fff3',
    'omarchy_boot.py': 'f7b10200f58f84922d1d993ace12e24c1f31e0d03f725c29871039c7ae0e3559',
    'omarchy_input.py': 'f9178533a1951dcf2da998cf477bd428dbfbeaeea92901aa76fef7fa13c59067',
    'omarchy_audio.py': 'eac4f59d05d203e86c34668f1393d0053e2a8888f6f994d539fca29c43a8b48d',
    'omarchy_android.py': 'bbdf818e97365a7e9633ef12519e027c534702a53d2ca7c8617e6b103afc6af4',
    'omarchy_android_client.py': 'e0daa3e8cb5114403641ee6e23087b41655c6ecf9365247f21d84313a0d17cd0',
}
FREEZE_SCOPE = frozenset(('omarchy_android.py',))
# Generation the reviewed resources update installed (its deliverable install map).
RESOURCES_RUNTIME_SHA = {
    'omarchy_proot.py': '4240de2a165af00be564f449c047a0e46614f4e9f4e1943756aa5d20f6e4d03a',
    'omarchy_commands.py': '81dd805e093d061f8159b2953fd2ebde553d90e10f31fe94412610e4ddc167fd',
    'omarchy.py': '304996e5d33c770a4d9cf2c28c6309bc0843af9d283b99a50d93d0e88707909f',
    'processes.py': 'fd9b51ebb267782ab4a5151298202b589f19f5bde2ebae6c515e16d484df7e5a',
    'omarchy_runtime.py': 'd209358f89c98ba91b8bfe2652a330058301dcee2951cc2328df29c3d20eaa5b',
    'omarchy_resources.py': '7cbdd53dd2c9ebbdc3a64cded5f6a52dcd3385a1f6f8cb3cce990b379b049e92',
    'omarchy_boot.py': '2966eeaf3b02c593a2638f2a13f0e3c069c43899e6da66b5bab37991b38f0203',
    'omarchy_input.py': 'baa102398d8b1525f5061eaccf27bad84b668d57e7875a59758eeda999df3389',
    'omarchy_audio.py': '3cebf98a8ee56f4b37a8edc2ccba8a481b303589d6dc4f188797f9309e7fe105',
    'omarchy_android.py': 'efb681f01380e55992838ca0178db801fc9ac06db3ec4ccb9c4216fad854584d',
    'omarchy_android_client.py': 'd564423e4ed197b88737662b0d8b90f61d65d34ba2ac3d467508ab5a64a63f9b',
}
# Generation the reviewed cccb8ac0 terminal installed, verified against the device
# install record and journals on 2026-10-20; the heal migration's only predecessor.
DEVICE_RUNTIME_SHA = {
    'omarchy_proot.py': '1215fadb98913703a0b092d4503ddcb2dab8a9be07e768716e3f226c685a66bc',
    'omarchy_commands.py': '7cbcbb5cfbebe88b15212aa07e071cd8d89c6931066d2b27881770831e7a96ab',
    'omarchy.py': '304996e5d33c770a4d9cf2c28c6309bc0843af9d283b99a50d93d0e88707909f',
    'processes.py': 'cda6028651ccb08a55bacf91c68186e4e9189bf9456cfd79ca587f354d3c946e',
    'omarchy_runtime.py': '4e5d0c2b9205491282a22673624b01f42eb88b5fe7628e2e29b34c887f4eb9d5',
    'omarchy_resources.py': 'e3276fcdd7af97cdc7286d7f694cac5bf9eff2d7b87dda679f661ef52499fff3',
    'omarchy_boot.py': 'f7b10200f58f84922d1d993ace12e24c1f31e0d03f725c29871039c7ae0e3559',
    'omarchy_input.py': 'baa102398d8b1525f5061eaccf27bad84b668d57e7875a59758eeda999df3389',
    'omarchy_audio.py': '3cebf98a8ee56f4b37a8edc2ccba8a481b303589d6dc4f188797f9309e7fe105',
    'omarchy_android.py': '89fb4bb6cb2c76e0350ea460303479ac2d076834b80674d0adb357f7c0b34fad',
    'omarchy_android_client.py': '6b0e9308e2b88337309450b7d32a3bc2963dbd4fcfbaf50c1e82dace20cb3823',
}
HEAL_SCOPE = frozenset(('omarchy.py', 'omarchy_audio.py', 'omarchy_commands.py',
                        'omarchy_input.py', 'omarchy_proot.py', 'omarchy_runtime.py'))
# Immutable setup08 predecessor, also recorded in runtime-install-device03.
PREVIOUS_RUNTIME_SHA = {
    'omarchy_proot.py': '4240de2a165af00be564f449c047a0e46614f4e9f4e1943756aa5d20f6e4d03a',
    'omarchy_commands.py': '81dd805e093d061f8159b2953fd2ebde553d90e10f31fe94412610e4ddc167fd',
    'omarchy.py': '304996e5d33c770a4d9cf2c28c6309bc0843af9d283b99a50d93d0e88707909f',
    'processes.py': '01b6307fb529348bd72666c3cb014a16c6e09df2f90deb3a79e2f2010d31c49e',
    'omarchy_runtime.py': '9505572efb220dc4c24d7e77a49c54cdb49b1abcccb88abcb95625653ca3f855',
    'omarchy_resources.py': '82cbc34975216e8cc08a61fb466d878deb129cb86f6ecff1303d2cc9dffc93d2',
    'omarchy_boot.py': '2966eeaf3b02c593a2638f2a13f0e3c069c43899e6da66b5bab37991b38f0203',
    'omarchy_input.py': 'baa102398d8b1525f5061eaccf27bad84b668d57e7875a59758eeda999df3389',
    'omarchy_audio.py': '3cebf98a8ee56f4b37a8edc2ccba8a481b303589d6dc4f188797f9309e7fe105',
    'omarchy_android.py': 'efb681f01380e55992838ca0178db801fc9ac06db3ec4ccb9c4216fad854584d',
    'omarchy_android_client.py': 'd564423e4ed197b88737662b0d8b90f61d65d34ba2ac3d467508ab5a64a63f9b',
}


def require(value, reason='runtime-update-boundary'):
    base.require(value, reason)


def read(fd, name, maximum=131072):
    try:
        with base.regular(name, maximum, fd) as source:
            before = base.fingerprint(os.fstat(source.fileno()))
            data = source.read()
            require(stat.S_IMODE(before[3]) == 0o600, 'runtime-update-file-mode')
            require(base.fingerprint(os.fstat(source.fileno())) == before
                    and base.fingerprint(os.stat(name, dir_fd=fd, follow_symlinks=False)) == before,
                    'runtime-update-concurrent-change')
            return {'fingerprint': before, 'sha256': hashlib.sha256(data).hexdigest()}, data
    except FileNotFoundError:
        return None, None


def snapshot(fd, name):
    return read(fd, name)[0]


def targets(fd):
    return {name: snapshot(fd, name) for name in (*OLD_NAMES, *NEW_NAMES)}


def matches(rows, pins):
    return all(rows[name] is not None and rows[name]['sha256'] == sha for name, sha in pins.items())


def stopped(fd, root):
    before, data = read(fd, 'runtime-state.json', 16384)
    require(before is not None, 'runtime-update-state-missing')
    state = json.loads(data)
    require(isinstance(state, dict) and state.get('schema') == 1
            and state.get('uid') == os.getuid() and state.get('root') == root
            and state.get('phase') == 'stopped' and state.get('terminationConfirmed') is True,
            'runtime-update-runtime-active')
    return before


def publish_target(fd, name, data, previous):
    require(snapshot(fd, name) == previous, 'runtime-update-target-changed')
    temporary = '.runtime-update-source-' + uuid.uuid4().hex
    target = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | base.NOFOLLOW, 0o600, dir_fd=fd)
    try:
        with os.fdopen(target, 'wb') as output:
            output.write(data); output.flush(); os.fsync(output.fileno())
        require(snapshot(fd, name) == previous, 'runtime-update-target-changed')
        if previous is None:
            base.publish(fd, temporary, name)
        else:
            os.replace(temporary, name, src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    finally:
        try:
            os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError:
            pass


def backup(fd, row, originals):
    os.mkdir(row['backupDirectory'], 0o700, dir_fd=fd)
    child = os.open(row['backupDirectory'], os.O_RDONLY | os.O_DIRECTORY | base.NOFOLLOW, dir_fd=fd)
    try:
        row['backupIdentity'] = base.identity(os.fstat(child))
        for name, (before, data) in originals.items():
            require(snapshot(fd, name) == before, 'runtime-update-backup-changed')
            target = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | base.NOFOLLOW, 0o600, dir_fd=child)
            with os.fdopen(target, 'wb') as output:
                output.write(data); output.flush(); os.fsync(output.fileno())
            copied, _ = read(child, name)
            require(copied['sha256'] == before['sha256'], 'runtime-update-backup-incomplete')
        os.fsync(child)
        os.fsync(fd)
    finally:
        os.close(child)


def persist(fd, row, previous, journal):
    installer.save_record(fd, row, previous, journal=journal)
    return copy.deepcopy(row)


def context(fd, root, prefix, installed, state):
    require(base.identity(root.lstat()) == installed['root']
            and base.identity(os.fstat(fd)) == installed['root'], 'runtime-update-root-replaced')
    base.check_installed(root, prefix, installed)
    require(stopped(fd, installed['root']) == state, 'runtime-update-state-changed')
    require(proot_guard.selection(root) is not None, 'runtime-update-guard-required')


def same_owned_identity(left, right):
    # /data st_dev drifts across boots on this device (observed 65084↔65096 with
    # stable inodes); owned identity is inode+uid, matching the proot guard's
    # remount tolerance. Same-boot inode changes still fail.
    return isinstance(left, list) and isinstance(right, list) and len(left) == 3 and len(right) == 3 \
        and left[1] == right[1] and left[2] == right[2] == os.getuid() \
        and all(type(item) is int and item >= 0 for item in (*left, *right))


def completed_record(value, installed, pins):
    return isinstance(value, dict) and value.get('schema') == 1 and value.get('phase') == 'INSTALLED' \
        and value.get('uid') == os.getuid() \
        and same_owned_identity(value.get('root'), installed.get('root')) \
        and same_owned_identity(value.get('rootfs'), installed.get('rootfs_identity')) \
        and value.get('runtime_files') == pins


def read_history(fd, installed, guarded_pins, tmpdir_pins, inventory_pins):
    originals = {name: read(fd, name, 16384)
                 for name in (JOURNAL, TMPDIR_JOURNAL, INVENTORY_JOURNAL, PROOT_TEMP_JOURNAL, RESOURCES_JOURNAL, HEAL_JOURNAL, VIDEO_JOURNAL, DIRECT_JOURNAL, FREEZE_JOURNAL)}
    first, second, third, fourth, fifth, sixth, seventh, eighth, ninth = [json.loads(data) if before is not None else None
                                   for before, data in originals.values()]
    if originals[JOURNAL][0] is not None:
        require(any(completed_record(first, installed, pins)
                for pins in (guarded_pins, tmpdir_pins, inventory_pins, PREVIOUS_RUNTIME_SHA, RESOURCES_RUNTIME_SHA, base.RUNTIME_SHA)), 'runtime-update-uncertain')
    if originals[TMPDIR_JOURNAL][0] is not None:
        require(any(completed_record(second, installed, pins) for pins in (tmpdir_pins, inventory_pins, PREVIOUS_RUNTIME_SHA, RESOURCES_RUNTIME_SHA, base.RUNTIME_SHA))
                and completed_record(first, installed, guarded_pins)
                and second.get('previous_runtime_files') == guarded_pins
                and second.get('previousJournal') == {'path': JOURNAL, 'sha256': originals[JOURNAL][0]['sha256']},
                'runtime-update-uncertain')
    if originals[INVENTORY_JOURNAL][0] is not None:
        require(any(completed_record(third, installed, pins) for pins in (inventory_pins, PREVIOUS_RUNTIME_SHA, RESOURCES_RUNTIME_SHA, base.RUNTIME_SHA))
                and completed_record(second, installed, tmpdir_pins)
                and third.get('previous_runtime_files') == tmpdir_pins
                and third.get('previousJournals') == {n: originals[n][0]['sha256'] for n in (JOURNAL, TMPDIR_JOURNAL)},
                'runtime-update-uncertain')
    if originals[PROOT_TEMP_JOURNAL][0] is not None:
        require(any(completed_record(fourth, installed, pins) for pins in (PREVIOUS_RUNTIME_SHA, RESOURCES_RUNTIME_SHA, base.RUNTIME_SHA))
                and completed_record(third, installed, inventory_pins)
                and fourth.get('previous_runtime_files') == inventory_pins
                and fourth.get('previousJournals') == {n: originals[n][0]['sha256']
                    for n in (JOURNAL, TMPDIR_JOURNAL, INVENTORY_JOURNAL)}, 'runtime-update-uncertain')
    if originals[RESOURCES_JOURNAL][0] is not None:
        previous = fourth or third or second or first
        require(completed_record(fifth, installed, RESOURCES_RUNTIME_SHA)
                and fifth.get('previous_runtime_files') == PREVIOUS_RUNTIME_SHA
                and (previous is None or completed_record(previous, installed, PREVIOUS_RUNTIME_SHA))
                and fifth.get('previousJournals') == {name: value[0]['sha256']
                    for name, value in originals.items()
                    if name not in (RESOURCES_JOURNAL, HEAL_JOURNAL, VIDEO_JOURNAL, DIRECT_JOURNAL, FREEZE_JOURNAL) and value[0] is not None},
                'runtime-update-uncertain')
    if originals[HEAL_JOURNAL][0] is not None:
        require(completed_record(sixth, installed, HEAL_RUNTIME_SHA)
                and sixth.get('previous_runtime_files') == DEVICE_RUNTIME_SHA
                and (fifth is None or completed_record(fifth, installed, RESOURCES_RUNTIME_SHA))
                and sixth.get('previousJournals') == {name: value[0]['sha256']
                    for name, value in originals.items()
                    if name not in (HEAL_JOURNAL, VIDEO_JOURNAL, DIRECT_JOURNAL, FREEZE_JOURNAL) and value[0] is not None},
                'runtime-update-uncertain')
    if originals[VIDEO_JOURNAL][0] is not None:
        require(completed_record(seventh, installed, VIDEO_RUNTIME_SHA)
                and seventh.get('previous_runtime_files') == HEAL_RUNTIME_SHA
                and completed_record(sixth, installed, HEAL_RUNTIME_SHA)
                and seventh.get('previousJournals') == {name: value[0]['sha256']
                    for name, value in originals.items()
                    if name not in (VIDEO_JOURNAL, DIRECT_JOURNAL, FREEZE_JOURNAL) and value[0] is not None},
                'runtime-update-uncertain')
    if originals[DIRECT_JOURNAL][0] is not None:
        require(completed_record(eighth, installed, DIRECT_RUNTIME_SHA)
                and eighth.get('previous_runtime_files') == VIDEO_RUNTIME_SHA
                and completed_record(seventh, installed, VIDEO_RUNTIME_SHA)
                and eighth.get('previousJournals') == {name: value[0]['sha256']
                    for name, value in originals.items()
                    if name not in (DIRECT_JOURNAL, FREEZE_JOURNAL) and value[0] is not None},
                'runtime-update-uncertain')
    if originals[FREEZE_JOURNAL][0] is not None:
        require(completed_record(ninth, installed, base.RUNTIME_SHA)
                and ninth.get('previous_runtime_files') == DIRECT_RUNTIME_SHA
                and completed_record(eighth, installed, DIRECT_RUNTIME_SHA)
                and ninth.get('previousJournals') == {name: value[0]['sha256']
                    for name, value in originals.items() if name != FREEZE_JOURNAL and value[0] is not None},
                'runtime-update-uncertain')
    return first, second, third, fourth, fifth, sixth, seventh, eighth, ninth, originals


def history_unchanged(fd, history):
    require(all(snapshot(fd, name) == value for name, value in history.items()), 'runtime-update-history-changed')


def update(sources, home, prefix):
    source = base.RuntimeSources(sources)
    require(set(source.data) == set((*OLD_NAMES, *NEW_NAMES))
            and set(base.RUNTIME_SHA) == set(source.data), 'runtime-update-source-scope')
    inventory_pins = dict(PREVIOUS_RUNTIME_SHA, **{'omarchy_commands.py': INVENTORY_COMMANDS_SHA})
    tmpdir_pins = dict(inventory_pins, **{'omarchy_resources.py': OLD_RESOURCES_SHA})
    old_pins = {name: tmpdir_pins[name] for name in OLD_NAMES}
    old_pins['omarchy_runtime.py'] = OLD_RUNTIME_SHA
    guarded_pins = dict(tmpdir_pins)
    guarded_pins['omarchy_commands.py'] = OLD_COMMANDS_SHA
    home, prefix = Path(home).resolve(strict=True), Path(prefix).resolve(strict=True)
    root, fd, locks = home / '.local/share/loopy-omarchy', None, []
    try:
        fd = base.walk(home, '.local/share/loopy-omarchy')
        require(fd is not None and stat.S_IMODE(os.fstat(fd).st_mode) == 0o700)
        # Established runtime locks must already exist; idempotence creates no files.
        for name in ('install.lock', 'runtime-control.lock'):
            require(snapshot(fd, name) is not None, 'runtime-update-lock-missing')
            locks.append(installer.lock(fd, name))
        original_install, install_data = read(fd, 'install.json', 32768)
        require(original_install is not None, 'runtime-update-install-missing')
        installed = json.loads(install_data)
        require(isinstance(installed, dict) and installed.get('schema') == 1
                and installed.get('phase') == 'INSTALLED' and installed.get('uid') == os.getuid()
                and installed.get('root') == base.identity(os.fstat(fd))
                and installed.get('home') == str(home) and installed.get('prefix') == str(prefix)
                and installed.get('container') == base.CONTAINER
                and installed.get('bundle_sha256') == base.OUTER_SHA, 'runtime-update-install-identity')
        state = stopped(fd, installed['root'])
        context(fd, root, prefix, installed, state)
        first, second, third, fourth, fifth, sixth, seventh, eighth, ninth, journal_originals = read_history(
            fd, installed, guarded_pins, tmpdir_pins, inventory_pins)
        current = targets(fd)
        if installed.get('runtime_files') == base.RUNTIME_SHA and matches(current, base.RUNTIME_SHA):
            latest = ninth or eighth or seventh or sixth or fifth or fourth or third or second or first
            require(latest is None or latest['runtime_files'] == base.RUNTIME_SHA,
                    'runtime-update-incomplete-history')
            return latest or dict(schema=1, phase='INSTALLED', uid=os.getuid(), root=installed['root'],
                                            runtime_files=dict(base.RUNTIME_SHA), backupDirectory=None)
        require(ninth is None, 'runtime-update-installed-changed')
        if installed.get('runtime_files') == DIRECT_RUNTIME_SHA and matches(current, DIRECT_RUNTIME_SHA):
            require({name for name in base.RUNTIME_SHA if base.RUNTIME_SHA[name] != DIRECT_RUNTIME_SHA.get(name)}
                    == FREEZE_SCOPE, 'runtime-update-freeze-scope')
            require(eighth is None or completed_record(eighth, installed, DIRECT_RUNTIME_SHA), 'runtime-update-original-mismatch')
            journal, previous_pins = FREEZE_JOURNAL, DIRECT_RUNTIME_SHA
        elif installed.get('runtime_files') == VIDEO_RUNTIME_SHA and matches(current, VIDEO_RUNTIME_SHA):
            require({name for name in base.RUNTIME_SHA if base.RUNTIME_SHA[name] != VIDEO_RUNTIME_SHA.get(name)}
                    == DIRECT_SCOPE, 'runtime-update-direct-scope')
            require(seventh is None or completed_record(seventh, installed, VIDEO_RUNTIME_SHA), 'runtime-update-original-mismatch')
            journal, previous_pins = DIRECT_JOURNAL, VIDEO_RUNTIME_SHA
        elif installed.get('runtime_files') == HEAL_RUNTIME_SHA and matches(current, HEAL_RUNTIME_SHA):
            require({name for name in base.RUNTIME_SHA if base.RUNTIME_SHA[name] != HEAL_RUNTIME_SHA.get(name)}
                    == VIDEO_SCOPE, 'runtime-update-video-scope')
            require(sixth is None or completed_record(sixth, installed, HEAL_RUNTIME_SHA), 'runtime-update-original-mismatch')
            journal, previous_pins = VIDEO_JOURNAL, HEAL_RUNTIME_SHA
        elif installed.get('runtime_files') == DEVICE_RUNTIME_SHA and matches(current, DEVICE_RUNTIME_SHA):
            require({name for name in base.RUNTIME_SHA if base.RUNTIME_SHA[name] != DEVICE_RUNTIME_SHA.get(name)}
                    == HEAL_SCOPE, 'runtime-update-heal-scope')
            require(fifth is None or completed_record(fifth, installed, RESOURCES_RUNTIME_SHA), 'runtime-update-original-mismatch')
            journal, previous_pins = HEAL_JOURNAL, DEVICE_RUNTIME_SHA
        elif installed.get('runtime_files') == PREVIOUS_RUNTIME_SHA and matches(current, PREVIOUS_RUNTIME_SHA):
            # Unreachable with current pins (more than the reviewed scope differs from
            # setup08 since dc45649); retained as the 10/09 updater generation's proven path.
            latest = fourth or third or second or first
            require(latest is None or completed_record(latest, installed, PREVIOUS_RUNTIME_SHA),
                    'runtime-update-original-mismatch')
            require({name for name in base.RUNTIME_SHA if base.RUNTIME_SHA[name] != PREVIOUS_RUNTIME_SHA[name]}
                    <= {'omarchy_runtime.py', 'omarchy_resources.py', 'processes.py'}, 'runtime-update-resources-scope')
            journal, previous_pins = RESOURCES_JOURNAL, PREVIOUS_RUNTIME_SHA
        elif installed.get('runtime_files') == inventory_pins and matches(current, inventory_pins):
            require(fourth is None, 'runtime-update-installed-changed')
            require(completed_record(third, installed, inventory_pins), 'runtime-update-original-mismatch')
            journal, previous_pins = PROOT_TEMP_JOURNAL, inventory_pins
        elif installed.get('runtime_files') == old_pins and matches(current, old_pins) \
                and all(current[name] is None for name in NEW_NAMES):
            require(first is None and second is None and third is None and fourth is None, 'runtime-update-installed-changed')
            journal, previous_pins = JOURNAL, old_pins
        elif installed.get('runtime_files') == guarded_pins and matches(current, guarded_pins):
            require(second is None and third is None and fourth is None and completed_record(first, installed, guarded_pins),
                    'runtime-update-original-mismatch')
            journal, previous_pins = TMPDIR_JOURNAL, guarded_pins
        else:
            require(installed.get('runtime_files') == tmpdir_pins and matches(current, tmpdir_pins)
                    and third is None and fourth is None and completed_record(second, installed, tmpdir_pins), 'runtime-update-original-mismatch')
            journal, previous_pins = INVENTORY_JOURNAL, tmpdir_pins
        changes = tuple(name for name in (*OLD_NAMES, *NEW_NAMES)
                        if previous_pins.get(name) != base.RUNTIME_SHA[name])
        history = {name: value[0] for name, value in journal_originals.items() if name != journal}
        originals = {name: read(fd, name) for name in changes if current[name] is not None}
        require(all(value[0] == current[name] for name, value in originals.items()))
        originals['install.json'] = (original_install, install_data)
        originals.update({name: journal_originals[name] for name, value in history.items() if value is not None})
        row = dict(schema=1, phase='BACKUP', uid=os.getuid(), root=installed['root'],
                   rootfs=installed['rootfs_identity'], runtime_files=dict(base.RUNTIME_SHA),
                   previous_runtime_files=previous_pins, backupDirectory='.runtime-update-' + uuid.uuid4().hex,
                   originals={name: value[0] for name, value in originals.items()}, applied=[])
        if journal == TMPDIR_JOURNAL:
            row['previousJournal'] = {'path': JOURNAL, 'sha256': journal_originals[JOURNAL][0]['sha256']}
        elif journal in (INVENTORY_JOURNAL, PROOT_TEMP_JOURNAL, RESOURCES_JOURNAL, HEAL_JOURNAL, VIDEO_JOURNAL, DIRECT_JOURNAL, FREEZE_JOURNAL):
            row['previousJournals'] = {name: value['sha256'] for name, value in history.items() if value is not None}
        context(fd, root, prefix, installed, state)
        history_unchanged(fd, history)
        require(targets(fd) == current and snapshot(fd, 'install.json') == original_install,
                'runtime-update-concurrent-change')
        saved = persist(fd, row, None, journal)
        try:
            backup(fd, row, originals)
            row['phase'] = 'UPDATING'; saved = persist(fd, row, saved, journal)
            for name in changes:
                context(fd, root, prefix, installed, state)
                history_unchanged(fd, history)
                require(targets(fd) == current and snapshot(fd, 'install.json') == original_install,
                        'runtime-update-concurrent-change')
                publish_target(fd, name, source.data[name], current[name])
                current[name] = snapshot(fd, name)
                row['applied'].append(name)
                saved = persist(fd, row, saved, journal)
            require(matches(targets(fd), base.RUNTIME_SHA), 'runtime-update-incomplete')
            context(fd, root, prefix, installed, state)
            history_unchanged(fd, history)
            final = dict(installed, runtime_files=dict(base.RUNTIME_SHA))
            publish_target(fd, 'install.json', json.dumps(final, sort_keys=True, separators=(',', ':')).encode(),
                           original_install)
            require(base.read_journal(fd) == final and not source.missing(fd), 'runtime-update-final-incomplete')
            base.check_installed(root, prefix, final)
            row['phase'] = 'INSTALLED'; persist(fd, row, saved, journal)
            return row
        except BaseException:
            row['phase'] = 'UPDATE_UNKNOWN'
            persist(fd, row, saved, journal)
            raise ValueError('runtime-update-uncertain') from None
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        raise ValueError('runtime-update-filesystem') from None
    finally:
        for lock in reversed(locks):
            os.close(lock)
        if fd is not None:
            os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Update the pinned stopped Omarchy runtime with the installed PRoot guard')
    parser.add_argument('--sources', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = update(args.sources, os.environ['HOME'], os.environ['PREFIX'])
    except (OSError, ValueError, SyntaxError) as error:
        print(json.dumps({'schema': 1, 'phase': 'FAILED', 'reason': str(error) if isinstance(error, ValueError)
                          else 'runtime-update-unavailable'}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
