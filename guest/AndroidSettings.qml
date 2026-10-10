import QtQuick
import Quickshell.Io
import qs.Commons

Column {
  id: root
  property string action: "wifi"
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family
  property string message: ""
  readonly property bool busy: request.running
  signal accepted()
  spacing: Style.space(10)

  function launch() {
    if (request.running || (action !== "wifi" && action !== "bluetooth")) return
    message = ""
    request.running = true
  }

  Text {
    width: parent.width
    text: root.message !== "" ? root.message : "Managed by Android"
    color: root.foreground
    font.family: root.fontFamily
    font.pixelSize: Style.font.body
    wrapMode: Text.WordWrap
  }

  Button {
    width: parent.width
    text: root.busy ? "Opening settings…" : "Open " + (root.action === "wifi" ? "Wi-Fi" : "Bluetooth") + " settings"
    foreground: root.foreground
    fontFamily: root.fontFamily
    bordered: true
    focusable: true
    enabled: !root.busy
    onClicked: root.launch()
  }

  Process {
    id: request
    command: ["omarchy-proot-settings", root.action]
    stdout: StdioCollector {
      onStreamFinished: {
        try {
          var result = JSON.parse(text)
          if (result.schema === 1 && result.action === root.action && result.status === "accepted") {
            root.accepted()
            return
          }
        } catch (error) {}
        root.message = "Settings could not open. Please try again."
      }
    }
    onExited: function(code, status) {
      if (code !== 0) root.message = "Settings could not open. Please try again."
    }
  }
}
