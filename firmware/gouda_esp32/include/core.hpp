#pragma once
#include <array>
#include <cstdint>
#include <cstring>

namespace gouda {
constexpr size_t kFrameSize=22;
enum Kind:uint8_t { Command=1, Arm=2, Disarm=3, Status=128 };
struct Frame { uint8_t kind=Command; uint64_t token=0; uint32_t seq=0; uint8_t motion=0, flags=0, fault=0; };
inline uint16_t crc(const uint8_t* p,size_t n) {
    uint16_t c=0xffff;
    while(n--){c^=uint16_t(*p++)<<8;for(int i=0;i<8;i++)c=c&0x8000?(c<<1)^0x1021:c<<1;}
    return c;
}
inline std::array<uint8_t,kFrameSize> encode(const Frame& f){
    std::array<uint8_t,kFrameSize> b{};
    b[0]=0xa5;b[1]=0x5a;b[2]=2;b[3]=f.kind;
    for(int i=0;i<8;i++) b[4+i]=f.token>>(8*i);
    for(int i=0;i<4;i++) b[12+i]=f.seq>>(8*i);
    b[16]=f.motion;b[17]=f.flags;b[18]=f.fault;
    auto c=crc(b.data(),20);b[20]=c&255;b[21]=c>>8;return b;
}
class Parser {
    std::array<uint8_t,kFrameSize> b{};size_t n=0;
public:
    bool feed(uint8_t v,Frame& f){
        b[n++]=v;
        if(n<kFrameSize)return false;
        const bool valid=b[0]==0xa5&&b[1]==0x5a&&b[2]==2&&b[19]==0&&
            crc(b.data(),20)==(uint16_t(b[20])|(uint16_t(b[21])<<8));
        if(!valid){memmove(b.data(),b.data()+1,--n);return false;}
        f=Frame{};f.kind=b[3];
        for(int i=0;i<8;i++)f.token|=uint64_t(b[4+i])<<(8*i);
        for(int i=0;i<4;i++)f.seq|=uint32_t(b[12+i])<<(8*i);
        f.motion=b[16];f.flags=b[17];f.fault=b[18];n=0;return true;
    }
};
struct Output{uint16_t x,y;};
class Core {
    uint32_t last_=0, stopped_=0, seq_=0;
    bool have_seq_=false, have_time_=false;
    std::array<Output,5> lut_;
public:
    uint64_t token;bool enabled=false, calibrated=false;uint8_t motion=0,fault=0;
    Core(uint64_t nonce,std::array<Output,5> lut,bool valid):lut_(lut),token(nonce),calibrated(valid){
        for(auto x:lut_)if(x.x>4095||x.y>4095)calibrated=false;
    }
    void disable(uint8_t reason,uint32_t now){
        enabled=false;motion=0;fault=reason;stopped_=now;have_time_=true;
        ++token;have_seq_=false;
    }
    void tick(uint32_t now){if(enabled&&uint32_t(now-last_)>=250)disable(1,now);}
    bool receive(const Frame& f,uint32_t now){
        tick(now);
        if(f.token!=token||f.motion>4||f.flags>1||f.fault!=0)return false;
        if(f.kind!=Command&&f.kind!=Arm&&f.kind!=Disarm)return false;
        if(have_seq_ && (uint32_t(f.seq-seq_)==0||uint32_t(f.seq-seq_)>=0x80000000u))return false;
        if(f.kind==Arm && (f.motion!=0||f.flags!=1||!calibrated||enabled))return false;
        if(f.kind==Command && f.flags && !enabled)return false;
        seq_=f.seq;have_seq_=true;
        if(f.kind==Disarm || (f.kind==Command && !f.flags)){disable(0,now);return true;}
        if(f.kind==Arm){enabled=true;motion=0;fault=0;stopped_=now-1000;have_time_=true;last_=now;return true;}
        last_=now;
        if(f.motion==0){if(motion!=0){stopped_=now;have_time_=true;}motion=0;return true;}
        // Direction changes require a fresh command after a neutral interval.
        // This is an electrical interlock, not a physical stop measurement.
        if(motion!=0&&motion!=f.motion){motion=0;stopped_=now;have_time_=true;return true;}
        if(motion==0&&have_time_&&uint32_t(now-stopped_)<1000)return true;
        motion=f.motion;return true;
    }
    Output output()const{return lut_[enabled?motion:0];}
    Frame status()const{return Frame{Status,token,seq_,motion,uint8_t(enabled),fault};}
};
}
