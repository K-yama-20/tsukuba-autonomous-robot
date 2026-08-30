#include "adi_imu_tr_driver_ros2/sample_counter_tracker.hpp"

#include <cstdlib>
#include <iostream>

namespace {

void Require(const bool condition, const char* message) {
  if (!condition) {
    std::cerr << "FAILED: " << message << '\n';
    std::exit(1);
  }
}

}  // namespace

int main() {
  using adi_imu_tr_driver_ros2::CounterDecision;
  using adi_imu_tr_driver_ros2::SampleCounterTracker;

  SampleCounterTracker tracker;
  Require(tracker.Observe(65534) == CounterDecision::kAccepted,
          "first counter must be accepted");
  Require(tracker.Observe(65535) == CounterDecision::kAccepted,
          "counter before wrap must be accepted");
  Require(tracker.Observe(0) == CounterDecision::kAccepted,
          "uint16 wrap must be accepted");
  Require(tracker.Observe(1) == CounterDecision::kAccepted,
          "counter after wrap must be accepted");
  Require(tracker.Observe(1) == CounterDecision::kDuplicate,
          "duplicate must be rejected");
  Require(tracker.Observe(4) == CounterDecision::kAccepted,
          "forward gap must keep the new sample");
  Require(tracker.inferred_drops() == 2, "two missing samples must be counted");
  Require(tracker.Observe(3) == CounterDecision::kOutOfOrder,
          "old sample must be rejected");
  Require(tracker.duplicates() == 1, "duplicate count must be retained");
  Require(tracker.out_of_order() == 1, "out-of-order count must be retained");
  tracker.Resynchronize();
  Require(tracker.Observe(100) == CounterDecision::kAccepted,
          "resynchronization must accept a new counter epoch");
  Require(tracker.inferred_drops() == 2 && tracker.out_of_order() == 1,
          "resynchronization must preserve diagnostic totals");

  std::cout << "Counter wrap/drop tests passed\n";
  return 0;
}
