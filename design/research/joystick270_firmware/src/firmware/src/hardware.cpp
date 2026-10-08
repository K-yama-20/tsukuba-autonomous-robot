#include "hardware.hpp"

#include <Wire.h>

#include <algorithm>
#include <cmath>

#include "hardware_config.hpp"

namespace emc270::firmware {

void Hardware::Begin() {
  pinMode(hw::kRelayPin, OUTPUT);
  digitalWrite(hw::kRelayPin, LOW);
  relay_energized_ = false;

  pinMode(hw::kDacCsPin, OUTPUT);
  digitalWrite(hw::kDacCsPin, HIGH);
  SPI.begin(hw::kDacSckPin, -1, hw::kDacMosiPin, hw::kDacCsPin);

  Wire.begin(hw::kI2cSdaPin, hw::kI2cSclPin, 400000);
  adc_available_ = ads_.begin(hw::kAds1015Address, &Wire);
  if (adc_available_) {
    ads_.setGain(GAIN_ONE); // +/-4.096 V at the divided ADC input.
    ads_.setDataRate(RATE_ADS1015_1600SPS);
  }
}

void Hardware::SetRelay(bool energized) {
  digitalWrite(hw::kRelayPin, energized ? HIGH : LOW);
  relay_energized_ = energized;
}

void Hardware::WriteDacMillivolts(std::uint16_t x_mv, std::uint16_t y_mv,
                                  std::uint16_t full_scale_mv) {
  WriteDacChannel(false, MillivoltsToCode(x_mv, full_scale_mv));
  WriteDacChannel(true, MillivoltsToCode(y_mv, full_scale_mv));
}

AdcReading Hardware::ReadActualMillivolts() {
  if (!adc_available_)
    return {};
  const auto raw_x = ads_.readADC_SingleEnded(0);
  const auto raw_y = ads_.readADC_SingleEnded(1);
  if (raw_x < 0 || raw_y < 0)
    return {};
  // R5/R6 and R7/R8 are 10 kOhm / 10 kOhm dividers. computeVolts()
  // reports the divided ADS1015 pin voltage, so multiply by two.
  const auto x_mv = static_cast<long>(
      std::lround(static_cast<double>(ads_.computeVolts(raw_x)) * 2000.0));
  const auto y_mv = static_cast<long>(
      std::lround(static_cast<double>(ads_.computeVolts(raw_y)) * 2000.0));
  AdcReading reading;
  reading.valid = x_mv >= 0 && x_mv <= 65535 && y_mv >= 0 && y_mv <= 65535;
  reading.x_mv = static_cast<std::uint16_t>(std::clamp<long>(x_mv, 0, 65535));
  reading.y_mv = static_cast<std::uint16_t>(std::clamp<long>(y_mv, 0, 65535));
  return reading;
}

void Hardware::WriteDacChannel(bool channel_b, std::uint16_t code) {
  // MCP4922: bit15=A/B, bit14=unbuffered, bit13=0 gives 2x gain,
  // bit12=active, bits11..0=data. LDAC is tied low in the KiCad design.
  const std::uint16_t word = static_cast<std::uint16_t>(
      (channel_b ? 0x8000U : 0U) | 0x1000U | (code & 0x0FFFU));
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWrite(hw::kDacCsPin, LOW);
  SPI.transfer16(word);
  digitalWrite(hw::kDacCsPin, HIGH);
  SPI.endTransaction();
}

std::uint16_t Hardware::MillivoltsToCode(std::uint16_t millivolts,
                                         std::uint16_t full_scale_mv) {
  if (full_scale_mv == 0)
    return 0;
  const auto clamped = std::min(millivolts, full_scale_mv);
  const auto code =
      (static_cast<std::uint32_t>(clamped) * 4096U + full_scale_mv / 2U) /
      full_scale_mv;
  return static_cast<std::uint16_t>(std::min<std::uint32_t>(4095U, code));
}

} // namespace emc270::firmware
