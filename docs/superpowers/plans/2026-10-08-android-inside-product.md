# Android inside product implementation plan

> Agentic workers use parallel source ownership and root-owned execution. Follow the existing TDD and verification workflow.

**Goal:** Connect actual Android applications to actual Omarchy Wayland windows with continuous pixels and native input.

**Architecture:** The GTK consumer connects to the actual same-UID Android app hub. A Binder ContentProvider verifies shell UID/PID and hands the accepted socket FD to the shell broker, with a GRANT binding before HELLO. Each connection owns one private display/task and a generation-bound typed protocol. The Android catalog and ordered guest action worker start the actual consumer. Both direct cross-domain socket directions were denied on the actual device and are not fallback routes.

**Tech stack:** Android Java/API36 reflection, AF_UNIX SO_PEERCRED, ImageReader/VirtualDisplay, GTK3/Wayland, Python3.

**Spec:** ../specs/2026-10-08-android-inside-product.md

## Constraints

Root owns SDK/JVM/ADB/build/install. No OS flash, roles, microphone grant, global input fallback, user HOME changes or saved app frames. Existing frozen receipts remain unchanged; use fresh execution paths. Keep modules below500lines. Completion of this phase does not complete all Omarchy support.

## Task1: Protocol and broker policy

Owner gpu_production: AndroidInsideWire.java, AndroidInsideBrokerPolicy.java, minimal SCROLL extension to AndroidInsideProtocol/Session, corresponding Java tests. Preserve original LIP1 bytes for existing actions. Length-bound typed HELLO/OPENED/ACK/FRAME/CLOSED/ERROR and exact frame retirement. Root captured preimplementation javac RED in android-inside-production-java-20261008-01/red.log. Root must compile/run both new test mains plus original93cases before package validation.

Binder adaptation also assigns AndroidInsideAppHub/Provider/Grant.java and pure Grant tests to this owner. Exported provider denies callers except actual UID2000 with matching Binder PID and active session. Returned original FD closes only after grant ACK or bounded expiry; it never shuts down the shared endpoint. Explicit ADB bootstrap remains session scoped and status must not claim a shell LISTEN socket.

## Task2: Actual shell display/input adapter

Owner remote_icon_failure: AndroidInsideShell/Display/Input.java. Actual shell context/oppackage, current PM target, owned VD flags/task/topUID, explicit focus observation and targeted input. Stream frames without files, retire only exact frame lease, close only owned resources. Root compiles against actualSDK and runs controlled public target; no general user-app content is exported.

## Task3: Actual GTK consumer

Owner gpu_gui_failure: inside_wire.py, inside_input.py, inside_window.py and Python tests. Consume the exact current 3-column catalog. Bind socket credential/birth and metadata, use a real Wayland ApplicationWindow, actual letterbox coordinates, balanced input, resize/focus/EOF/close. Root verifies continuous display and actual input separately from draw/presentation/performance claims.

## Task4: Product launch integration

Root: AndroidApps PM UID thirdcolumn, AndroidAppCatalog inside default plus explicit external entry, OmarchySessionBridge assets, DesktopCommands/android-inside and Hyprland action, native DesktopMenus. RED: `python3 -B -m unittest tests.test_android_app_tasks.AndroidAppTaskTests.test_inside_catalog_uses_real_uid_and_keeps_external_route_explicit`; RED: `python3 -B -m unittest tests.test_inside_launcher`. GREEN: Android app task/compat/platform and inside launcher tests. Guest rejects all extra/injected action fields and keeps argv fixed/base64 only.

## Task5: Exact artifact and device verification

Root rebuilds using current matched cache-files/VirGL/Wayland candidates and unchanged default runtime. Preserve source checks and exact native entry hashes, place APK/receipt in fresh no-clobber deliverable. Update only after authoritative unsaved-work check permits; preserve data/settings and revalidate118/configuration/services/roles/mic. Actual public target must use the canonical production broker/consumer and verify pixels, general input, resize/focus/close and owned cleanup. ADB-disconnect persistence and actual physical/notion/performance acceptance remain separate evidence until executed.
