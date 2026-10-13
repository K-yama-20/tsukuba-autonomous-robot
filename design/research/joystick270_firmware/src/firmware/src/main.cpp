#include <Arduino.h>

#include "controller_app.hpp"

namespace {

emc270::firmware::ControllerApp app;

} // namespace

void setup() { app.Begin(); }

void loop() { app.Loop(); }
