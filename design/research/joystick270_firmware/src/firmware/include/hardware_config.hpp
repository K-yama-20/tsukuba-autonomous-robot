#pragma once

#include <cstdint>

namespace emc270::hw {

constexpr int kDacCsPin = 5;
constexpr int kDacSckPin = 18;
constexpr int kDacMosiPin = 23;
constexpr int kRelayPin = 32;
constexpr int kI2cSdaPin = 21;
constexpr int kI2cSclPin = 22;
constexpr int kEncoderUartRxPin = 33; // J11-3
constexpr int kEncoderUartTxPin = 13; // J11-4

constexpr std::uint32_t kPcBaud = 460800;
constexpr std::uint32_t kEncoderBaud = 230400;
constexpr std::uint8_t kAds1015Address = 0x48;
constexpr std::uint32_t kControlPeriodMs = 20;
constexpr std::uint32_t kStatusPeriodMs = 100;
constexpr std::uint32_t kEncoderStaleMs = 200;
constexpr std::uint32_t kArmNeutralHoldMs = 500;
constexpr std::uint32_t kRelaySettleMs = 30;
constexpr std::uint32_t kFailsafeRelayDelayMs = 10;
constexpr std::int16_t kArmNeutralCommandLimit = 100;

} // namespace emc270::hw
