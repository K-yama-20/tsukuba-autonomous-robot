#include <Arduino.h>
#include <Bluepad32.h>
#include <SPI.h>

#include "control.hpp"
#include "settings.hpp"

constexpr int kRelay = 32;
constexpr int kDacCs = 5;
ControllerPtr controller = nullptr;
motion::Session session;
motion::Voltage lastOutput{0xffff, 0xffff};

void writeOutput(motion::Voltage value) {
    if (value.x == lastOutput.x && value.y == lastOutput.y) return;
    const uint16_t x = motion::dacCode(value.x, settings::kXFullScaleMv);
    const uint16_t y = motion::dacCode(value.y, settings::kYFullScaleMv);
    SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
    digitalWrite(kDacCs, LOW);
    SPI.transfer16(0x1000 | x);  // MCP4922 A -> R1: steering
    digitalWrite(kDacCs, HIGH);
    digitalWrite(kDacCs, LOW);
    SPI.transfer16(0x9000 | y);  // MCP4922 B -> R2: forward/reverse
    digitalWrite(kDacCs, HIGH);
    SPI.endTransaction();
    lastOutput = value;
}

void stop() {
    session.reset();
    writeOutput({motion::kNeutralMv, motion::kNeutralMv});
}

void onConnected(ControllerPtr candidate) {
    // getModel() uses properties loaded at connection time. isGamepad() uses
    // HID report data, which may not exist yet (especially after a reboot).
    if (controller ||
        candidate->getModel() != Controller::CONTROLLER_TYPE_PS5Controller) {
        Serial.println("BT REJECT: another controller is active or model is not DualSense");
        candidate->disconnect();
        return;
    }
    controller = candidate;
    stop();
    Serial.println("DualSense connected. Waiting for input; center the left stick to operate.");
}

void onDisconnected(ControllerPtr candidate) {
    if (candidate != controller) return;
    controller = nullptr;
    stop();
    Serial.println("DualSense disconnected: SET X=2500 Y=2500 mV");
}

void setup() {
    // Relay is physically bypassed; leave its driver OFF.
    digitalWrite(kRelay, LOW);
    pinMode(kRelay, OUTPUT);
    pinMode(21, INPUT_PULLUP);
    pinMode(22, INPUT_PULLUP);
    digitalWrite(kDacCs, HIGH);
    pinMode(kDacCs, OUTPUT);
    SPI.begin(18, -1, 23, kDacCs);
    stop();  // Write stop voltage before starting the Bluetooth connection logic.

    Serial.begin(115200);
    Serial.println("BOOT reconnect-fix-1: SET X=2500 Y=2500 mV (requested, not measured)");
    BP32.setup(&onConnected, &onDisconnected);
    // Preserve stored pairing keys so a paired DualSense can reconnect.
    BP32.enableVirtualDevice(false);
    BP32.enableNewBluetoothConnections(true);
}

void loop() {
    const bool updated = BP32.update();
    const uint32_t now = millis();
    if (controller && controller->isConnected()) {
        if (updated && controller->hasData()) {
            if (controller->isGamepad())
                session.report(controller->axisX(), controller->axisY(), now);
            else
                stop();
        }
        const motion::Vector target = session.target(now);
        writeOutput(motion::map(target, settings::kRightPolarity,
                               settings::kForwardPolarity));
    } else {
        stop();
    }
    delay(1);
}
