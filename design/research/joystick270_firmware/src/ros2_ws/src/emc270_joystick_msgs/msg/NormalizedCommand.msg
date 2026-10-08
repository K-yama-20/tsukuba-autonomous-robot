std_msgs/Header header

# Independent square-limited joystick commands. Both values are clamped to
# [-1.0, +1.0]. x: left(-)/right(+), y: reverse(-)/forward(+).
float32 x
float32 y
bool arm
