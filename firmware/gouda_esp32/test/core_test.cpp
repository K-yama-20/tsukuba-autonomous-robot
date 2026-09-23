#include "core.hpp"
#include <cassert>
#include <iostream>
using namespace gouda;
Core make(){return Core(123,{{{2000,2001},{2000,2200},{2000,1800},{1800,2001},{2200,2001}}},true);}
int main(){
    const uint8_t text[]="123456789";assert(crc(text,9)==0x29b1);
    auto c=make();assert(!c.enabled&&c.output().x==2000);
    assert(!c.receive({Command,123,1,1,1,0},0));
    assert(c.receive({Arm,123,1,0,1,0},0));
    for(uint32_t t=50;t<=1000;t+=50)assert(c.receive({Command,123,t,1,1,0},t));
    assert(c.motion==1&&c.output().y==2200);
    assert(!c.receive({Command,123,1000,1,1,0},1100));
    c.tick(1249);assert(c.enabled);c.tick(1250);assert(!c.enabled&&c.motion==0&&c.token==124);
    assert(!c.receive({Arm,123,1001,0,1,0},1300));
    assert(c.receive({Arm,124,0,0,1,0},1300));
    auto w=make();assert(w.receive({Arm,123,0,0,1,0},0xfffffff0));
    w.tick(0xe9);assert(w.enabled);w.tick(0xea);assert(!w.enabled);
    auto u=make();u.calibrated=false;assert(!u.receive({Arm,123,1,0,1,0},0));
    Parser parser;Frame out;auto b=encode({Command,99,27,4,1,0});
    parser.feed(0,out);for(size_t i=0;i<b.size();i++)assert(parser.feed(b[i],out)==(i==b.size()-1));
    assert(out.token==99&&out.motion==4&&out.seq==27);
    b[17]^=4;for(auto v:b)assert(!parser.feed(v,out));
    auto s=make();s.receive({Arm,123,0,0,1,0},0);for(uint32_t t=50;t<=1000;t+=50)s.receive({Command,123,t,1,1,0},t);
    s.receive({Command,123,1001,3,1,0},1001);assert(s.motion==0);
    for(uint32_t t=1050;t<=1950;t+=50)s.receive({Command,123,t,3,1,0},t);
    assert(s.motion==0);s.receive({Command,123,2001,0,1,0},2001);assert(s.motion==0);
    std::cout<<"core boundary, replay, calibration, parser, switch tests passed\n";
}
