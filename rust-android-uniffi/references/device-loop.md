# Device loop

## Real phone over wireless adb

```sh
adb connect <phone>:5555
adb -s <phone>:5555 install -r app/build/outputs/apk/debug/app-debug.apk
adb -s <phone>:5555 shell dumpsys package <pkg> | grep -E 'lastUpdateTime|versionName'   # proves the install
```

Always pass `-s` when more than one device is attached. Compare
`lastUpdateTime` with the APK's mtime: an install that printed "Success" from
a stale APK path proves nothing.

## Reaching a dev backend from the phone

| Situation | Approach |
|---|---|
| Phone attached over adb (USB or wireless) | `adb reverse tcp:8080 tcp:8080`, build with API URL `http://localhost:8080` |
| Emulator on the same host | `http://10.0.2.2:8080` |
| Phone away from the laptop | Tailscale: `tailscale serve --bg --tcp <port> tcp://127.0.0.1:8080` or an http serve, URL `http://<host>.<tailnet>.ts.net:<port>` |

- `adb reverse` works over wireless adb too, so the server can stay bound to
  127.0.0.1.
- With Tailscale the only way in is through the tailnet, and the server stays
  off every other network.
- Android blocks cleartext http unless the host is listed:

```xml
<!-- res/xml/network_security.xml, referenced from the manifest's networkSecurityConfig -->
<network-security-config>
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="false">10.0.2.2</domain>
        <domain includeSubdomains="false">localhost</domain>
        <domain includeSubdomains="true">ts.net</domain>
    </domain-config>
</network-security-config>
```

Keep release builds on https. Scope this file to debug with a `src/debug/`
overlay if release must not carry it.

Check reachability before blaming the app: `curl` the URL from the laptop,
then from the phone, e.g.
`adb shell 'echo -e "GET / HTTP/1.0\r\n\r\n" | nc -w 3 127.0.0.1 8080'`.

## Headless emulators

```sh
setsid nohup emulator -avd <avd> -no-window -no-audio -no-snapshot-save \
  -gpu swiftshader_indirect -port 5570 > emu.log 2>&1 < /dev/null &
adb -s emulator-5570 wait-for-device
until [ "$(adb -s emulator-5570 shell getprop sys.boot_completed | tr -d '\r')" = 1 ]; do sleep 3; done
```

- `setsid ... < /dev/null` detaches the emulator, so the tool shell can exit.
- Pick an explicit `-port`, so you never collide with emulators you do not
  own.
- `swiftshader_indirect` works without a host GPU. The MediaPipe GPU delegate
  may still refuse, so let the app fall back to CPU.
- Grant runtime permissions without UI: `adb shell pm grant <pkg> android.permission.CAMERA`.
- Launch without knowing the activity name:
  `adb shell cmd package resolve-activity --brief <pkg> | tail -1`, then
  `am start -W -n <that>`, or `monkey -p <pkg> 1`.
- Screenshots: `adb exec-out screencap -p > s.png`. Downscale before looking
  at them (`magick s.png -resize 800x s_small.png`).
- Drive the UI with `adb shell input tap X Y` and `input text`, using
  coordinates from a screenshot at native resolution.

## Emulators on another machine

When a workstation lacks KVM or RAM, run emulators on a beefier host and
drive them over ssh:

```sh
scp app-debug.apk app-debug-androidTest.apk host:/tmp/app/
ssh host 'export ANDROID_SERIAL=emulator-5556; cd /tmp/app && adb install -r -t app-debug.apk && adb install -r -t app-debug-androidTest.apk'
ssh host 'ANDROID_SERIAL=emulator-5556 adb shell am instrument -w -e class <pkg>.SomeTest <pkg>.test/androidx.test.runner.AndroidJUnitRunner'
```

Before claiming one, check which package is in the foreground of each
emulator (`dumpsys activity activities | grep topResumedActivity`). Pin
yourself to one serial.

## Dev server lifecycle

```sh
PID=$(pgrep -x my-server); [ -n "$PID" ] && kill "$PID"; sleep 1
ENV=... setsid nohup /path/to/target/debug/my-server > server.log 2>&1 < /dev/null &
sleep 2; pgrep -x my-server; tail -2 server.log
```

`pgrep -x` matches the process name exactly. `pkill -f target/debug/my-server`
also matches the bash command line that contains that string, and kills your
own shell (exit 144).

When client and server share a version constant (a protocol or rules
version), rebuild and redeploy both in the same step. An old client against a
new server fails every request.
