#include <Arduino.h>
#include <SPI.h>
#include "esp_system.h"
#include "core.hpp"
#include "calibration.hpp"

constexpr int kRelay=32,kDacCs=5;
gouda::Core* core=nullptr;
gouda::Parser parser;
gouda::Output previous{0xffff,0xffff};
uint32_t lastStatus=0;

void output(gouda::Output value){
    if(value.x==previous.x&&value.y==previous.y)return;
    // Reused from Joystick270_DualSense writeOutput: MCP4922 A=X, B=Y,
    // 1 MHz SPI mode 0, SCK18/MOSI23/CS5, gain/control words unchanged.
    SPI.beginTransaction(SPISettings(1000000,MSBFIRST,SPI_MODE0));
    digitalWrite(kDacCs,LOW);SPI.transfer16(0x1000|value.x);digitalWrite(kDacCs,HIGH);
    digitalWrite(kDacCs,LOW);SPI.transfer16(0x9000|value.y);digitalWrite(kDacCs,HIGH);
    SPI.endTransaction();previous=value;
}
void setup(){
    // Existing hardware has a relay bypass. LOW is not a physical isolation claim.
    digitalWrite(kRelay,LOW);pinMode(kRelay,OUTPUT);
    pinMode(21,INPUT_PULLUP);pinMode(22,INPUT_PULLUP);
    digitalWrite(kDacCs,HIGH);pinMode(kDacCs,OUTPUT);SPI.begin(18,-1,23,kDacCs);
    static gouda::Core state((uint64_t(esp_random())<<32)|esp_random(),calibration::table(),calibration::validated);
    core=&state;output(core->output());
    Serial.begin(115200);
}
void loop(){
    const uint32_t now=millis();
    // Bound parser work so a continuous corrupt stream cannot starve watchdog.
    for(int i=0;i<256&&Serial.available();i++){
        gouda::Frame f;if(parser.feed(Serial.read(),f))core->receive(f,now);
    }
    core->tick(now);output(core->output());
    if(uint32_t(now-lastStatus)>=50){auto data=gouda::encode(core->status());Serial.write(data.data(),data.size());lastStatus=now;}
    delay(1);
}
