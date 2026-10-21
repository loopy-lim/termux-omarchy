import QtQuick
import QtTest

TestCase {
  id: test
  name: "MenuDataBeforeOpen"
  property var host
  property var queue
  Component {
    id: hostFactory
    QtObject {
      property bool rowsLoaded: false
      property var startup
      property var opened: []
      function open(payload) {
        if (startup.defer(payload)) return
        opened = opened.concat([payload])
      }
      function close() { startup.cancel() }
    }
  }
  function init() {
    host = hostFactory.createObject(test)
    var component = Qt.createComponent("../../android/assets/omarchy-bridge/MenuStartupQueue.qml")
    compare(component.status, Component.Ready, component.errorString())
    queue = component.createObject(test, { host: host })
    verify(queue !== null)
    host.startup = queue
  }
  function cleanup() { if (queue) queue.destroy(); if (host) host.destroy(); queue = null; host = null }
  function test_apps_payload_waits_for_rows() {
    host.open('{"menu":"apps"}')
    compare(host.opened.length, 0)
    host.rowsLoaded = true
    tryVerify(function() { return host.opened.length === 1 })
    compare(host.opened[0], '{"menu":"apps"}')
  }
  function test_close_cancels_open_before_rows() {
    host.open('{"menu":"apps"}')
    host.close()
    host.rowsLoaded = true
    wait(20)
    compare(host.opened.length, 0)
    host.open('{"menu":"root"}')
    compare(host.opened[0], '{"menu":"root"}')
  }
}
