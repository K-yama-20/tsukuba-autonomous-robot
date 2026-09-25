// Pipe-only firmware emulator for host integration tests. Never touches a device.
#include "control.hpp"
#include <chrono>
#include <thread>
#include <fcntl.h>
#include <unistd.h>
int main() {
    using namespace gouda_usb;
    Core core(0xabcdef123456789ULL); Parser parser;
    fcntl(STDIN_FILENO,F_SETFL,O_NONBLOCK);
    const auto start=std::chrono::steady_clock::now(); uint32_t previous=0,seq=0;
    core.bluetooth_connected(0);
    while (true) {
        auto now=uint32_t(std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start).count());
        core.bluetooth_report(0,0,now);
        uint8_t b[256];auto n=read(STDIN_FILENO,b,sizeof b);
        if(n==0)return 0;
        for(ssize_t i=0;i<n;++i){Frame frame;if(parser.feed(b[i],frame))core.receive(frame,now);}
        core.tick(now);
        if(now-previous>=20){auto bytes=encode(make_status(core.boot_token(),seq++,now,core.status(now)));if(write(STDOUT_FILENO,bytes.data(),bytes.size())!=ssize_t(bytes.size()))return 1;previous=now;}
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
}
