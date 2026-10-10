"""Reproduce guest adapters and Korean input configuration from public text."""
from prepare_runtime_payloads import archive, encoded, match_artifacts, read, require, sha

GUEST = {
    'usr/local/lib/loopy-omarchy/processes.py': ('runtime/processes.py', 0o600, None),
    'usr/local/lib/loopy-omarchy/omarchy_audio_guest.py': ('guest/omarchy_audio_guest.py', 0o600, None),
    'usr/local/lib/loopy-omarchy/omarchy_android_client.py': ('runtime/omarchy_android_client.py', 0o600, None),
    'usr/local/bin/omarchy-proot-audio': ('guest/omarchy-proot-audio', 0o700, None),
    'usr/local/bin/omarchy-proot-settings': ('runtime/omarchy-proot-settings', 0o700, None),
    'usr/share/omarchy/shell/Ui/AndroidSettings.qml': ('guest/AndroidSettings.qml', 0o600, None),
    'usr/share/omarchy/shell/plugins/panels/network/Panel.qml': ('guest/shell/plugins/panels/network/Panel.qml', 0o644, '0f68955cb5123450b7ae4e4a0de7be6f3920a9c0f57b208689aca1a2c16f9532'),
    'usr/share/omarchy/shell/plugins/panels/bluetooth/Panel.qml': ('guest/shell/plugins/panels/bluetooth/Panel.qml', 0o644, 'f51654a00e3bfe5d6ccfd42bbd972d9436f70a27d152baa43ccdcbd8c66e1225'),
    'usr/share/omarchy/shell/Ui/qmldir': ('guest/shell/Ui/qmldir', 0o644, 'd6b4ac284aea719458cfdcf66afc18c63b69c20a400317ad307d029865a96886'),
    'home/omarchy/.config/hypr/looknfeel.lua': ('guest/looknfeel.lua', 0o644, 'd36d5ae6fe6a3b57424a26295d7b04861fcee4dd54d0403e3be6f5fe729e3273'),
    'usr/share/omarchy/bin/omarchy-launch-browser': ('guest/omarchy-launch-browser', 0o755, '3db9315b614ec7d58d048e702543f3126321c2b8d8dd659430ca02453e5b1a4b'),
}
INPUT = {
    'home/omarchy/.config/fcitx5/profile': ('guest/korean_input/profile', 0o600, None),
    'home/omarchy/.config/gtk-3.0/settings.ini': ('guest/korean_input/settings.ini', 0o644, None),
    'home/omarchy/.config/gtk-4.0/settings.ini': ('guest/korean_input/settings.ini', 0o644, None),
    'home/omarchy/.config/hypr/autostart.lua': ('guest/korean_input/autostart.lua', 0o644, 'a3320bdbe91bdd2335a27f25d0cfd0c2b2af1fa525ee7e9dbafb1f11d81188c5'),
    'home/omarchy/.config/hypr/ime.lua': ('guest/korean_input/ime.lua', 0o644, None),
}
DEFINITIONS = {
    'guest': (GUEST, 'guest-audio-android-settings', 'guest'),
    'inputConfig': (INPUT, 'guest-korean-input-config', 'input-config'),
}


def prepare(root, name, component):
    require(name in DEFINITIONS, 'preparation-guest-component')
    targets, label, basename = DEFINITIONS[name]
    names = {source for source, _, _ in targets.values()}
    require(set(component['sources']) == names, 'preparation-source-members')
    sources = {}
    for source in sorted(names):
        data = read(root, source)
        require(component['sources'][source] == {'bytes': len(data), 'sha256': sha(data)},
                'preparation-source-hash')
        if source.endswith('.py'):
            compile(data, source, 'exec')  # No guest worker or runtime module is executed.
        sources[source] = data
    files, manifest = {}, {'schema': 1, 'component': label, 'files': {}}
    for target, (source, mode, before) in sorted(targets.items()):
        data = sources[source]
        files[target] = (data, 0o600)
        manifest['files'][target] = {'sha256': sha(data), 'mode': mode, 'before': before}
    artifacts = {basename + '-payload.tar': archive(files), basename + '-manifest.json': encoded(manifest)}
    match_artifacts(artifacts, component['artifacts'])
    return artifacts
