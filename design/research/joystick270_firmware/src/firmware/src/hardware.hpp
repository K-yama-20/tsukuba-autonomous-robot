#pragma once

#include <Adafruit_ADS1X15.h>
#include <Arduino.h>
#include <SPI.h>

#include <cstdint>

namespace emc270::firmware {

struct AdcReading {
  bool valid{false};
  std::uint16_t x_mv{0};
  std::uint16_t y_mv{0};
};

class Hardware {
public:
  void Begin();
  void SetRelay(bool energized);
  bool relay_energized() const { return relay_energized_; }
  void WriteDacMillivolts(std::uint16_t x_mv, std::uint16_t y_mv,
                          std::uint16_t full_scale_mv);
  AdcReading ReadActualMillivolts();
  bool adc_available() const { return adc_available_; }

private:
  void WriteDacChannel(bool channel_b, std::uint16_t code);
  static std::uint16_t MillivoltsToCode(std::uint16_t millivolts,
                                        std::uint16_t full_scale_mv);

  Adafruit_ADS1015 ads_{};
  bool adc_available_{false};
  bool relay_energized_{false};
};

} // namespace emc270::firmware
