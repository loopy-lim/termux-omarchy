import QtQuick
import QtTest

TestCase {
  id: test
  name: "OriginalPluginStartupRequests"
  property var registry
  property var host
  property var queue

  Component {
    id: registryFactory
    QtObject {
      property bool scanning: true
      signal scanFinished()
    }
  }
  Component {
    id: hostFactory
    QtObject {
      property bool pluginReloading: false
      property var startup
      property var events: []
      property var afterEvent
      function summon(id, payload) {
        var held = startup.intercept("summon", id, payload)
        if (held !== 0) return held > 0
        events = events.concat([["summon", id, payload]])
        if (afterEvent) afterEvent()
        return true
      }
      function hide(id) {
        var held = startup.intercept("hide", id, "")
        if (held !== 0) return held > 0
        events = events.concat([["hide", id, ""]])
        return true
      }
      function toggle(id, payload) {
        var held = startup.intercept("toggle", id, payload)
        if (held !== 0) return held > 0
        events = events.concat([["toggle", id, payload]])
        return true
      }
    }
  }

  function init() {
    registry = registryFactory.createObject(test)
    host = hostFactory.createObject(test)
    var component = Qt.createComponent("../../android/assets/omarchy-bridge/PluginStartupQueue.qml")
    compare(component.status, Component.Ready, "Real startup queue: " + component.errorString())
    queue = component.createObject(test, { registry: registry, host: host, timeoutMs: 1000 })
    verify(queue !== null)
    host.startup = queue
  }
  function cleanup() {
    if (queue) queue.destroy()
    if (host) host.destroy()
    if (registry) registry.destroy()
    queue = null; host = null; registry = null
  }
  function scanned() { registry.scanning = false; registry.scanFinished() }

  function test_first_request_survives_real_scan_signal_once() {
    verify(host.summon("omarchy.menu", '{"menu":"apps"}'))
    compare(host.events.length, 0)
    scanned()
    tryVerify(function() { return host.events.length === 1 })
    compare(JSON.stringify(host.events), JSON.stringify([["summon", "omarchy.menu", '{"menu":"apps"}']]))
    registry.scanFinished(); wait(20)
    compare(host.events.length, 1)
  }
  function test_order_payload_and_reload_gate() {
    host.pluginReloading = true
    var text = '{"message":"quotes \\" and 한국어"}'
    verify(host.summon("omarchy.osd", text))
    verify(host.hide("omarchy.osd"))
    verify(host.toggle("omarchy.menu", '{"menu":"apps"}'))
    scanned(); wait(20); compare(host.events.length, 0)
    host.pluginReloading = false
    tryVerify(function() { return host.events.length === 3 })
    compare(JSON.stringify(host.events), JSON.stringify([
      ["summon", "omarchy.osd", text], ["hide", "omarchy.osd", ""],
      ["toggle", "omarchy.menu", '{"menu":"apps"}']]))
    verify(host.hide("omarchy.menu")); compare(host.events.length, 4)
  }
  function test_bound_and_deadline_do_not_replay_expired_work() {
    queue.timeoutMs = 30
    for (var i = 0; i < 64; i++) verify(host.summon("omarchy.menu", String(i)))
    verify(!host.summon("omarchy.menu", "overflow"))
    wait(80); scanned(); wait(20)
    compare(host.events.length, 0)
    verify(host.summon("omarchy.menu", "fresh"))
    compare(JSON.stringify(host.events), JSON.stringify([["summon", "omarchy.menu", "fresh"]]))
  }
  function test_payload_budget_and_unknown_operation_are_rejected() {
    compare(queue.intercept("not-a-method", "omarchy.menu", ""), -1)
    compare(queue.intercept("summon", "", ""), -1)
    compare(queue.intercept("summon", "omarchy.menu", "x".repeat(262145)), -1)
    scanned(); wait(20); compare(host.events.length, 0)
  }
  function test_new_scan_during_replay_keeps_remaining_requests() {
    host.afterEvent = function() { if (host.events.length === 1) registry.scanning = true }
    verify(host.summon("omarchy.menu", "first"))
    verify(host.summon("omarchy.menu", "second"))
    scanned()
    tryVerify(function() { return host.events.length === 1 })
    wait(20); compare(host.events.length, 1)
    scanned()
    tryVerify(function() { return host.events.length === 2 })
    compare(host.events[1][2], "second")
  }
  function test_fresh_request_does_not_overtake_deferred_flush() {
    verify(host.summon("omarchy.menu", "held"))
    scanned()
    verify(host.summon("omarchy.menu", "fresh"))
    compare(JSON.stringify(host.events), JSON.stringify([
      ["summon", "omarchy.menu", "held"], ["summon", "omarchy.menu", "fresh"]]))
  }
}
