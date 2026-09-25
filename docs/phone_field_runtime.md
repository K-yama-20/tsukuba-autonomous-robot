# Phone field runtime

The phone gateway is a separate process on port 8443. It starts without RViz and stays available while the Gouda observation or autonomy profile is stopped. Its lifecycle adapter is `gouda_gui.runtime.runtime_status()` / `runtime_action(payload)`; the gateway must authenticate remote requests and enforce same-origin before calling it. The allowed actions are `start_observe`, `start_autonomy`, `stop`, `restart`, and `apply_config`. `restart` accepts only `profile: observation|autonomy`; `apply_config` restarts the current profile after loading the saved host settings. No action accepts a shell command, arbitrary path, navigation goal, or drive request.

Starting the autonomy profile starts the existing autonomy process and its readiness gates. It does not start a vehicle goal. Actual movement still requires the existing authenticated explicit goal request and the backend's recording, sensor freshness, calibration, and controller-state gates.

`stop`, `restart`, and `apply_config` refuse to interrupt an active or finalizing recording, active mapping, or autonomy with an active/retained goal. If processing is live but the backend state endpoint is missing or unreadable, these actions fail closed. Finish recording and confirm its output; stop mapping and preserve its result; then cancel autonomy and confirm a terminal state before a lifecycle restart. The separate lifecycle lock prevents overlapping phone actions. Runtime process signaling remains limited to PIDs whose boot ID and process start time match Gouda's saved ownership record.

Headless commands can be run after the normal workspace setup:

```bash
GOUDA_HEADLESS=1 bash scripts/gouda.sh observe
GOUDA_HEADLESS=1 bash scripts/gouda.sh autonomy
```

RViz remains the normal default when a desktop exists. The phone gateway service installer is opt-in and writes only a per-user systemd unit; it is not run by setup/build commands and does not edit system services:

```bash
bash scripts/install_phone_gateway_service.sh
systemctl --user status gouda-phone-gateway.service
```

The installer reads `$GOUDA_WORKSPACE/bags/gouda/phone-access/phone-access.json`, including its complete `gateway_arguments` array and exact TLS/key/token paths. It passes the configured arguments directly, including the explicit allowed-host set, without shell splitting or enabling broad private-host access. It restricts the private key and token to mode 0600 and refuses to overwrite an existing unit or wrapper. User services start after login by default. Starting them at boot before login is a separate opt-in command: `sudo loginctl enable-linger "$(id -un)"`. The installer does not run it or change system services. Removing the service is explicit: `systemctl --user disable --now gouda-phone-gateway.service` and remove the generated unit and wrapper.

## Phone network access on x86

Do not assume the host can provide a Wi-Fi hotspot. Inspect the actual adapter capability first:

```bash
nmcli -f GENERAL.DEVICE,GENERAL.TYPE,WIFI-PROPERTIES.AP device show
nmcli -f DEVICE,TYPE,STATE,CONNECTION device status
```

If no Wi-Fi adapter reports AP capability, direct phone-to-host Wi-Fi is unavailable on that host. Any hotspot setup is a separate manual NetworkManager operation: preserve the LiDAR Ethernet connection and routing, and verify its existing interface/address after setup. This runtime work does not create or modify network connections. In the supplied x86 inventory, only `enp0s5` and `enx6c6e0754b24a` Ethernet adapters were observed; AP capability remains unverified.
