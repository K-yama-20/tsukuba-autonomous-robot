#include <cassert>
#include <pty.h>
#include <termios.h>
#include <unistd.h>
#include "adis_rcv_bin.h"

int main() {
  int master, slave; char name[128];
  assert(openpty(&master, &slave, name, nullptr, nullptr) == 0);
  termios original{}; assert(tcgetattr(slave, &original) == 0);
  cfsetispeed(&original, B115200); cfsetospeed(&original, B115200);
  original.c_lflag |= ICANON | ECHO;
  assert(tcsetattr(slave, TCSANOW, &original) == 0);
  for (int n=0; n<32; ++n) {
    AdisRcvBin imu; assert(imu.Open(name));
    termios active{}; assert(tcgetattr(slave, &active) == 0);
    assert(cfgetispeed(&active) == B115200);
    assert(cfgetospeed(&active) == B115200);
    assert((active.c_cflag & (CLOCAL | CREAD)) == (CLOCAL | CREAD));
    assert(!(active.c_lflag & (ICANON | ECHO)));
    assert(active.c_cc[VMIN] == 0 && active.c_cc[VTIME] == 10);
    imu.Close();
    termios restored{}; assert(tcgetattr(slave, &restored) == 0);
    assert(restored.c_cflag == original.c_cflag);
    assert(restored.c_lflag == original.c_lflag);
    assert(cfgetospeed(&restored) == B115200);
  }
  close(slave); close(master);
}
