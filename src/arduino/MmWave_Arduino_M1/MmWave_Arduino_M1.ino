#include <Arduino.h>
#include "Seeed_Arduino_mmWave.h"

#define mmWaveSerial Serial1

SEEED_MR60BHA2 mmWave;

float breathRate = 0;
float heartRate = 0;
float distance = 0;

float tmpBreathRate = 0;
float tmpHeartRate = 0;
float tmpDistance = 0;

void setup() {
  Serial.begin(115200);
  mmWaveSerial.begin(115200, SERIAL_8N1, 17, 16);
  mmWave.begin(&mmWaveSerial);
}

void loop() {
  if (mmWave.update(500)) {
    if (mmWave.getBreathRate(tmpBreathRate)) {
      breathRate = tmpBreathRate;
    }
    if (mmWave.getHeartRate(tmpHeartRate)) {
      heartRate = tmpHeartRate;
    }
    if (mmWave.getDistance(tmpDistance)) {
      distance = tmpDistance;
    }

    Serial.printf("Breath Rate: %.0f || Heart Rate: %.0f || Distance: %.2f\n", breathRate, heartRate, distance);
  }
}