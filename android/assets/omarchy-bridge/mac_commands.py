"""Bounded Mac editing semantics. Never reinterpret Ctrl+C on the physical keyboard."""
import loopy_chords

# Key names resolved to native evdev codes by the session editing keyboard.
KEYS = {
    'copy': ('c', ('ctrl',)), 'paste': ('v', ('ctrl',)), 'paste_plain': ('v', ('ctrl', 'shift')),
    'cut': ('x', ('ctrl',)), 'select_all': ('a', ('ctrl',)), 'undo': ('z', ('ctrl',)),
    'redo': ('z', ('ctrl', 'shift')), 'find': ('f', ('ctrl',)), 'find_next': ('g', ('ctrl',)),
    'find_prev': ('g', ('ctrl', 'shift')), 'location': ('l', ('ctrl',)), 'save': ('s', ('ctrl',)),
    'save_as': ('s', ('ctrl', 'shift')), 'open': ('o', ('ctrl',)), 'new': ('n', ('ctrl',)),
    'new_window': ('n', ('ctrl', 'shift')), 'new_tab': ('t', ('ctrl',)), 'reopen_tab': ('t', ('ctrl', 'shift')),
    'reload': ('r', ('ctrl',)), 'print': ('p', ('ctrl',)), 'close': ('w', ('ctrl',)),
    'docstart': ('Home', ('ctrl',)), 'docend': ('End', ('ctrl',)), 'linestart': ('Home', ()),
    'lineend': ('End', ()), 'wordleft': ('Left', ('ctrl',)), 'wordright': ('Right', ('ctrl',)),
    'deleteword': ('BackSpace', ('ctrl',)), 'zoom_in': ('plus', ('ctrl',)),
    'zoom_out': ('minus', ('ctrl',)), 'zoom_reset': ('0', ('ctrl',)),
}
for operation in ('docstart', 'docend', 'linestart', 'lineend', 'wordleft', 'wordright'):
    key, mods = KEYS[operation]
    KEYS['select_' + operation] = (key, (*mods, 'shift'))
OPERATIONS = frozenset(KEYS) | {'quit', 'minimize', 'deleteline'}


def focused(tree):
    if tree.get('focused') and tree.get('app_id'):
        return tree
    for child in tree.get('nodes', []) + tree.get('floating_nodes', []):
        result = focused(child)
        if result: return result
    return None


def execute(operation, sway):
    if operation not in OPERATIONS: raise ValueError('Unsupported Mac command')
    window = focused(sway('get_tree', query=True))
    if not window or type(window.get('id')) is not int or window['id'] <= 0:
        raise ValueError('Mac command has no focused application')
    terminal = window['app_id'] in {'foot', 'loopy-terminal', 'loopy-code', 'loopy-monitor', 'loopy-cli-files'}
    if operation in ('quit', 'minimize') or operation == 'close' and terminal:
        sway('[con_id=%d] %s' % (window['id'], 'move scratchpad' if operation == 'minimize' else 'kill'))
        return
    if operation == 'deleteline':
        sequence = [('u', ('ctrl',))] if terminal else [('Home', ('shift',)), ('BackSpace', ())]
    else:
        key, modifiers = KEYS[operation]
        if terminal and operation in ('copy', 'paste'): modifiers = ('ctrl', 'shift')
        sequence = [(key, modifiers)]
    loopy_chords.inject(sequence)
