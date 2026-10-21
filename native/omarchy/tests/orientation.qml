import QtQuick
import Quickshell
import Quickshell.Wayland

ShellRoot {
    PanelWindow {
        anchors { top: true; bottom: true; left: true; right: true }
        exclusiveZone: 0
        WlrLayershell.namespace: "loopy-owned-output-orientation"
        WlrLayershell.layer: WlrLayer.Overlay
        color: "#ff0000"
        Rectangle {
            x: 0; y: parent.height / 2
            width: parent.width; height: parent.height / 2
            color: "#00ff00"
        }
    }
}
