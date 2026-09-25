#include <Arduino.h>
#include <Bluepad32.h>
#include <SPI.h>
#include <esp_system.h>
#include <new>
#include "control.hpp"
#include "protocol.hpp"

// Retain the validated Joystick270 pin assignment and bypass relay state.
constexpr int kRelayPin = 32;
constexpr int kDacCsPin = 5;
constexpr int kDacSckPin = 18;
constexpr int kDacMosiPin = 23;
constexpr uint32_t kStatusPeriodMs = 50;
constexpr size_t kMaxSerialBytesPerLoop = 256;
ControllerPtr controller = nullptr;
alignas(gouda_usb::Core) uint8_t core_storage[sizeof(gouda_usb::Core)];
gouda_usb::Core* core = nullptr;
gouda_usb::Parser parser;
gouda_usb::Voltage last_voltage{0xffff, 0xffff};
uint32_t last_status_ms = 0;
uint32_t status_sequence = 0;

uint64_t make_boot_token() {
    uint64_t token = (uint64_t(esp_random()) << 32) | uint64_t(esp_random());
    return token ? token : 1;
}

void write_output(gouda_usb::Voltage voltage) {
    if (voltage.x == last_voltage.x && voltage.y == last_voltage.y) return;
    const uint16_t x = gouda_usb::dac_code(voltage.x);
    const uint16_t y = gouda_usb::dac_code(voltage.y);
    SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
    digitalWrite(kDacCsPin, LOW);
    SPI.transfer16(0x1000 | x);  // MCP4922 A -> R1/X steering.
    digitalWrite(kDacCsPin, HIGH);
    digitalWrite(kDacCsPin, LOW);
    SPI.transfer16(0x9000 | y);  // MCP4922 B -> R2/Y forward/reverse.
    digitalWrite(kDacCsPin, HIGH);
    SPI.endTransaction();
    last_voltage = voltage;
}

void on_connected(ControllerPtr candidate) {
    // Match the known DualSense by model now; Bluepad32's gamepad/HID report
    // may not exist until the first input event after a reboot/reconnect.
    if (controller || candidate->getModel() != Controller::CONTROLLER_TYPE_PS5Controller) {
        candidate->disconnect();
        return;
    }
    controller = candidate;
    core->bluetooth_connected(millis());
}

void on_disconnected(ControllerPtr candidate) {
    if (candidate != controller) return;
    controller = nullptr;
    core->bluetooth_disconnected(millis());
}

void setup() {
    // Existing hardware is relay-bypassed. Keep the relay driver LOW; it is not
    // an MCU-visible emergency stop and this firmware makes no such claim.
    digitalWrite(kRelayPin, LOW);
    pinMode(kRelayPin, OUTPUT);
    pinMode(21, INPUT_PULLUP);
    pinMode(22, INPUT_PULLUP);
    digitalWrite(kDacCsPin, HIGH);
    pinMode(kDacCsPin, OUTPUT);
    SPI.begin(kDacSckPin, -1, kDacMosiPin, kDacCsPin);
    core = new (core_storage) gouda_usb::Core(make_boot_token());
    write_output(core->output(millis()).requested);  // stop request before Bluetooth starts.

    Serial.setTxBufferSize(256);
    Serial.setRxBufferSize(512);
    Serial.begin(115200);
    // USB/serial carries v3 frames only; do not print boot, pairing, or status text.
    BP32.setup(&on_connected, &on_disconnected);
    BP32.enableVirtualDevice(false);
    BP32.enableNewBluetoothConnections(true);
}

void loop() {
    const bool updated = BP32.update();
    const uint32_t now = millis();
    if (controller && controller->isConnected()) {
        if (updated && controller->hasData()) {
            if (controller->isGamepad()) core->bluetooth_report(controller->axisX(), controller->axisY(), now);
            else core->bluetooth_disconnected(now);
        }
    } else if (controller) {
        core->bluetooth_disconnected(now);
        controller = nullptr;
    }

    // Bound RX work; framing, CRC and field validation happen before state changes.
    for (size_t i = 0; i < kMaxSerialBytesPerLoop && Serial.available() > 0; ++i) {
        gouda_usb::Frame frame;
        if (parser.feed(static_cast<uint8_t>(Serial.read()), frame)) core->receive(frame, now);
    }

    core->tick(now);
    write_output(core->output(now).requested);
    if (uint32_t(now - last_status_ms) >= kStatusPeriodMs) {
        const auto status = gouda_usb::make_status(core->boot_token(), status_sequence++, now, core->status(now));
        const auto bytes = gouda_usb::encode(status);
        // Never wait for the host serial reader. Drop this status sample if the
        // TX ring cannot take a complete frame; the next periodic sample follows.
        if (Serial.availableForWrite() >= static_cast<int>(bytes.size()))
            Serial.write(bytes.data(), bytes.size());
        last_status_ms = now;
    }
    delay(1);
}
