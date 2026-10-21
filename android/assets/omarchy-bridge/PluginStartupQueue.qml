import QtQuick

// Keep early IPC requests in this shell instance until its real registry is ready.
Item {
  id: startup
  required property var registry
  required property var host
  property bool initialScanComplete: false
  property var pending: []
  property int payloadChars: 0
  property int timeoutMs: 60000
  property bool flushing: false
  readonly property bool ready: initialScanComplete && !registry.scanning && !host.pluginReloading

  // 0: call the original method; 1: accepted for replay; -1: rejected.
  function intercept(action, pluginId, payloadJson) {
    if (ready) {
      flush()
      return 0
    }
    var id = String(pluginId || "")
    var payload = String(payloadJson || "")
    if (["summon", "hide", "toggle"].indexOf(action) === -1 || !id || id.length > 256
        || payload.length > 262144 || pending.length >= 64 || payloadChars + payload.length > 1048576)
      return -1
    pending = pending.concat([{ action: action, id: id, payload: payload }])
    payloadChars += payload.length
    if (!expiry.running) expiry.start()
    return 1
  }

  function flush() {
    if (flushing || !ready) return
    flushing = true
    try {
      while (ready && pending.length) {
        var request = pending[0]
        pending = pending.slice(1)
        payloadChars -= request.payload.length
        host[request.action](request.id, request.payload)
      }
    } finally {
      flushing = false
      if (!pending.length) expiry.stop()
    }
  }

  onReadyChanged: if (ready) Qt.callLater(flush)
  Connections {
    target: startup.registry
    function onScanFinished() {
      startup.initialScanComplete = true
      Qt.callLater(startup.flush)
    }
  }
  Timer {
    id: expiry
    interval: Math.max(1, Math.min(60000, startup.timeoutMs))
    onTriggered: {
      console.warn("Shell startup requests expired before plugin registration:", startup.pending.length)
      startup.pending = []
      startup.payloadChars = 0
    }
  }
}
