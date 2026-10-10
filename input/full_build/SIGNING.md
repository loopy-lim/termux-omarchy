# Experimental delivery signing identity

The builder produces unsigned output and never installs an application. The
alpha.2 release candidate was separately signed after its clean build; its
signature, 16 KiB native-library alignment and all 440 unchanged payload entries
were checked. See the [input source inventory](../../manifests/input-sources.json)
for exact unsigned/signed APK and companion identities. Signing and offline
source rebuilding do not establish physical acceptance of that candidate.

The pinned upstream source includes its **public, untrusted development signing
identity**, not an exclusive developer identity:

| Item | Identity |
| --- | --- |
| Upstream commit | `6d3c6883265b4ec8092673e6d2d61ef86cab5405` |
| Source path | `lorie-app/testkey_untrusted.jks` |
| Git blob | `174cc95acd605bf557f9e63983f55fadc5ae44bd` |
| File SHA-256 | `a2ba19f2417de94dd3bdfb6ceece070cdc5f9b492af09cd5900058e860b18c7d` |
| Certificate SHA-256 | `b6da01480eefd5fbf2cd3771b8d1021ec791304bdd6c4bf41d3faabad48ee5e1` |
| Certificate-only input | `termux-public-certificate.txt` |
| Java certificate array hash | `-611922116` |

The [Termux GitHub installation documentation](https://github.com/termux/termux-app/blob/master/README.md#github)
publishes this certificate fingerprint and explains the public test-key trust
boundary. Its public availability permits compatible development builds; it
does not establish that a fork was produced or endorsed by the Termux team.
Any fork release must identify itself and its changed source clearly.

The [pinned Termux:X11 instructions](https://github.com/termux/termux-x11/blob/6d3c6883265b4ec8092673e6d2d61ef86cab5405/README.md#avoiding-slowdowns)
limit the sharedUid variant to GitHub-family Termux installations. The
`com.termux.x11` package with shared UID `com.termux` requires matching
certificates. F-Droid and Google Play installations have different signing
identities and must not be treated as compatible.

The smallest compatible route is to review a newly built sharedUid APK and its
source, then independently obtain the pinned public upstream identity in an
isolated build directory, verify both file and certificate pins, and sign that
new source build. No key material needs to be copied into this public repository.
The shell-loader companion must come from the same reviewed source and carry
the matching certificate metadata. Record the source, unsigned payload, signed
APK, companion, certificate and build-tool identities. Verify alignment,
signatures and unchanged APK payloads after signing.

The complete source build also rebuilds the companion loader; its `SIGNATURE`
constant is checked against the certificate-only input. An arbitrary APT nightly
companion is not evidence of compatibility. Delivery must pin the exact rebuilt
companion package hash from the same build receipt and retain its package version
in the installation receipt. The companion's loader is executed by Termux's
`app_process` path and is distinct from the installed application APK.

Existing installations with the exact matching certificate and shared UID can
be candidates for an in-place update with a reviewed nondecreasing version code.
Installation acceptance still needs verification for the exact resulting APK.
Preserve application data and preferences; do not uninstall, clear data or
replace a differently signed Termux installation to force compatibility.

The standalone flavor retains the Java/native input changes and reads its
optional marker through `Activity.getFilesDir()`. It is a possible separately
tested compatibility route, but changing an existing package's shared UID is
not an ordinary update. It also changes the shared-process scheduling behavior.
It must not silently replace the reviewed sharedUid delivery route.

The input helper needs Android 8/API 26 or later; the complete desktop
distribution requires Android 9/API 28 or later because of its guard build.
Upstream manifest minimum 24 alone is not proof of Android 7 compatibility.
