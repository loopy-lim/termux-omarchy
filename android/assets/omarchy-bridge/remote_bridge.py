"""Open endpoint-only SSH/RDP/VNC tools in the genuine Omarchy Wayland session."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))


def main(arguments=None):
    arguments = sys.argv[1:] if arguments is None else arguments
    if arguments not in (['ssh'], ['desktop']):
        raise ValueError('Choose ssh or desktop')
    os.environ['GDK_BACKEND'] = 'wayland'
    if arguments == ['ssh']:
        import remote_connections
        return remote_connections.main()
    import remote_desktop
    return remote_desktop.main()


if __name__ == '__main__':
    raise SystemExit(main())
