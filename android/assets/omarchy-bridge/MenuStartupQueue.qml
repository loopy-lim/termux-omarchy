import QtQuick

// The original menu resolves routes against asynchronously loaded JSONC rows.
Item {
  id: startup
  required property var host
  readonly property bool ready: host.rowsLoaded
  property var pending: []
  property int payloadChars: 0
  property bool flushing: false

  function defer(payloadJson) {
    if (ready) { flush(); return false }
    var payload = String(payloadJson || "")
    if (pending.length >= 64 || payload.length > 262144 || payloadChars + payload.length > 1048576) {
      console.warn("Menu startup request budget exceeded")
      return true
    }
    pending = pending.concat([payload])
    payloadChars += payload.length
    if (!expiry.running) expiry.start()
    return true
  }
  function cancel() { pending = []; payloadChars = 0; expiry.stop() }
  function flush() {
    if (!ready || flushing) return
    flushing = true
    try {
      while (ready && pending.length) {
        var payload = pending[0]
        pending = pending.slice(1)
        payloadChars -= payload.length
        host.open(payload)
      }
    } finally {
      flushing = false
      if (!pending.length) expiry.stop()
    }
  }
  onReadyChanged: if (ready) Qt.callLater(flush)
  Timer {
    id: expiry
    interval: 60000
    onTriggered: {
      console.warn("Menu requests expired before menu rows loaded:", startup.pending.length)
      startup.cancel()
    }
  }
}
