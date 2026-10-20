#include <Arduino.h>
#include "Seeed_Arduino_mmWave.h"

#ifdef ESP32
#  include <HardwareSerial.h>
HardwareSerial mmWaveSerial(0);
#else
#  define mmWaveSerial Serial1
#endif

SEEED_MR60BHA2 mmWave;

float breathRate = 0;
float heartRate = 0;
float distance = 0;

void setup() {
  Serial.begin(115200);
  mmWave.begin(&mmWaveSerial);
}

void loop() {
  if (mmWave.update(0)) {
    if (mmWave.getBreathRate(breathRate)) {
      Serial.printf("Breath Rate: %.2f\n", breathRate);
    }

    if (mmWave.getHeartRate(heartRate)) {
      Serial.printf("Heart Rate: %.2f\n", heartRate);
    }
    
    if (mmWave.getDistance(distance)) {
      Serial.printf("Distance: %.2f\n", distance);
    }
  }
}