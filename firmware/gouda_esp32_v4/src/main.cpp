// Gouda ESP32 firmware v4 (ND-17) — hardware glue around gouda_v4::Core. Design: design/docs/esp32_protocol_v4.md.
//
// Bluetooth gamepad via Bluepad32 (left stick: x right+, y forward+) -> Core::btReport; PC over USB serial (460800 8N1)
// -> Core::feed; Core::tick at the control period; the applied DAC codes go to the MCP4922 (A = X / steering, B = Y /
// forward) over SPI. Relay GPIO32 stays LOW (relay unused, DEC-037). While the configuration is invalid the DAC is never
// written. Configuration: NVS ("gouda_v4"/"cfg": 20 bytes items + generation + CRC) if valid, else the generated
// build-time items (include/gouda_v4/build_config.hpp). SET_CONFIG from the PC replaces and persists it.
// No emergency-stop input, detection or reporting (RQ-I072).
#include <Arduino.h>
#include <Bluepad32.h>
#include <Preferences.h>
#include <SPI.h>
#include "esp_system.h"
#include "gouda_v4/build_config.hpp"
#include "gouda_v4/control.hpp"

namespace {
constexpr int kRelayPin = 32, kDacCsPin = 5, kSckPin = 18, kMosiPin = 23;
constexpr uint32_t kSerialBaud = 460800;       // link setting of protocol v4 (not a vehicle value)
constexpr uint32_t kControlPeriodMs = 5;       // scheduling granularity of Core::tick; all timeouts come from the configuration
constexpr size_t kMaxBytesPerLoop = 512;       // bounded parser work per loop so a corrupt stream cannot starve the watchdogs
constexpr int32_t kStickRange = 512;           // Bluepad32 axis range -512..511

Preferences prefs;
ControllerPtr controller = nullptr;
gouda_v4::Core* core = nullptr;
uint16_t lastDacX = 0xFFFF, lastDacY = 0xFFFF;
bool btConnectedPending = false, btDisconnectedPending = false;

void writeDac(uint16_t x, uint16_t y) {
    if (x == lastDacX && y == lastDacY) return;
    SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
    digitalWrite(kDacCsPin, LOW); SPI.transfer16(uint16_t(0x1000 | (x & 0x0FFF))); digitalWrite(kDacCsPin, HIGH);   // A: X (steering), gain 1x, active
    digitalWrite(kDacCsPin, LOW); SPI.transfer16(uint16_t(0x9000 | (y & 0x0FFF))); digitalWrite(kDacCsPin, HIGH);   // B: Y (forward/reverse)
    SPI.endTransaction();
    lastDacX = x; lastDacY = y;
}

bool loadNvs(gouda_v4::Config& out, uint8_t& generation) {
    uint8_t blob[23];
    if (prefs.getBytesLength("cfg") != sizeof blob) return false;
    prefs.getBytes("cfg", blob, sizeof blob);
    if (gouda_v4::crc16(blob, 21) != gouda_v4::get16(blob + 21)) return false;
    out = gouda_v4::Config::fromBytes(blob); generation = blob[20];
    return out.valid();
}
bool saveNvs(const gouda_v4::Config& c, uint8_t generation) {
    uint8_t blob[23]; c.toBytes(blob); blob[20] = generation; gouda_v4::put16(blob + 21, gouda_v4::crc16(blob, 21));
    return prefs.putBytes("cfg", blob, sizeof blob) == sizeof blob;
}

void onConnected(ControllerPtr c) {
    // Model check at connect (HID report data may not exist yet, see the previous firmware's reconnect note); one gamepad only.
    if (controller || !c->isGamepad() && c->getModel() == 0) { c->disconnect(); return; }
    controller = c; btConnectedPending = true;
}
void onDisconnected(ControllerPtr c) { if (c != controller) return; controller = nullptr; btDisconnectedPending = true; }
}  // namespace

void setup() {
    digitalWrite(kRelayPin, LOW); pinMode(kRelayPin, OUTPUT);      // relay unused (DEC-037); driver kept off
    pinMode(21, INPUT_PULLUP); pinMode(22, INPUT_PULLUP);
    digitalWrite(kDacCsPin, HIGH); pinMode(kDacCsPin, OUTPUT); SPI.begin(kSckPin, -1, kMosiPin, kDacCsPin);
    prefs.begin("gouda_v4", false);
    gouda_v4::Config cfg; uint8_t gen = 0; bool fromNvs = loadNvs(cfg, gen);
    const gouda_v4::Config* initial = nullptr;
    if (fromNvs) initial = &cfg;
    else if (gouda_v4::build_config::has_config) { cfg = gouda_v4::Config::fromItems(gouda_v4::build_config::items); initial = &cfg; }
    static gouda_v4::Core instance(esp_random() ? esp_random() : 1u, initial, fromNvs, millis());
    core = &instance; if (fromNvs) core->setConfigGeneration(gen);
    // Neutral before anything else: with a valid configuration the DAC is written now; without one it is left untouched.
    gouda_v4::Applied a = core->applied(); if (a.dac_written) writeDac(a.dac_x, a.dac_y);
    Serial.begin(kSerialBaud);
    BP32.setup(&onConnected, &onDisconnected);
    BP32.enableVirtualDevice(false);
    BP32.enableNewBluetoothConnections(true);   // stored pairing keys are preserved
}

void loop() {
    const uint32_t now = millis();
    // ---- PC serial ----
    uint8_t buf[64]; size_t total = 0;
    while (total < kMaxBytesPerLoop && Serial.available()) { size_t n = Serial.read(buf, sizeof buf); if (!n) break; core->feed(buf, n, now); total += n; }
    // ---- Bluetooth gamepad ----
    const bool updated = BP32.update();
    if (btConnectedPending) { core->btConnect(now); btConnectedPending = false; }
    if (btDisconnectedPending) { core->btDisconnect(now); btDisconnectedPending = false; }
    if (controller && controller->isConnected() && updated && controller->hasData() && controller->isGamepad()) {
        int32_t x = controller->axisX(), y = -controller->axisY();   // Bluepad32: up is negative -> forward positive
        core->btReport(gouda_v4::clampAxis(x * gouda_v4::kAxisLimit / kStickRange), gouda_v4::clampAxis(y * gouda_v4::kAxisLimit / kStickRange), now);
    }
    // ---- control period ----
    static uint32_t lastTick = 0;
    if (uint32_t(now - lastTick) >= kControlPeriodMs) { core->tick(now); lastTick = now; }
    gouda_v4::Applied a = core->applied(); if (a.dac_written) writeDac(a.dac_x, a.dac_y);
    if (core->configChanged()) { saveNvs(core->config(), core->configGeneration()); core->clearConfigChanged(); }
    if (core->txSize()) { Serial.write(core->txData(), core->txSize()); core->txClear(); }
    delay(1);
}
