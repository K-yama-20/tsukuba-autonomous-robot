#pragma once

#include <cstdint>

namespace adi_imu_tr_driver_ros2 {

enum class CounterDecision {
  kAccepted,
  kDuplicate,
  kOutOfOrder,
};

// Tracks a wrapping uint16 sensor counter. Forward differences 1..32768 are
// accepted (including 65535 -> 0); larger modular differences are old data.
class SampleCounterTracker {
 public:
  CounterDecision Observe(const std::uint16_t counter) {
    if (!have_counter_) {
      have_counter_ = true;
      last_counter_ = counter;
      return CounterDecision::kAccepted;
    }
    const std::uint16_t delta = static_cast<std::uint16_t>(counter - last_counter_);
    if (delta == 0) {
      ++duplicates_;
      return CounterDecision::kDuplicate;
    }
    if (delta > 32768U) {
      ++out_of_order_;
      return CounterDecision::kOutOfOrder;
    }
    if (delta > 1) inferred_drops_ += static_cast<std::uint64_t>(delta - 1);
    last_counter_ = counter;
    return CounterDecision::kAccepted;
  }

  void Reset() {
    Resynchronize();
    duplicates_ = 0;
    out_of_order_ = 0;
    inferred_drops_ = 0;
  }

  void Resynchronize() {
    have_counter_ = false;
    last_counter_ = 0;
  }

  [[nodiscard]] std::uint64_t duplicates() const { return duplicates_; }
  [[nodiscard]] std::uint64_t out_of_order() const { return out_of_order_; }
  [[nodiscard]] std::uint64_t inferred_drops() const { return inferred_drops_; }

 private:
  bool have_counter_{false};
  std::uint16_t last_counter_{0};
  std::uint64_t duplicates_{0};
  std::uint64_t out_of_order_{0};
  std::uint64_t inferred_drops_{0};
};

}  // namespace adi_imu_tr_driver_ros2
