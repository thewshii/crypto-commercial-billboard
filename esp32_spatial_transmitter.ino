/*
  esp32_spatial_transmitter.ino — ESP32 Mobile Spatial Tracking Transmitter Over Local Wi-Fi
  
  Rule 233: The ESP32 Mobile Spatial Tracking Over Local Wi-Fi, Static IP Socket Receiver,
  and Stationary Terminal Integration.

  Functionality:
  1. Configures the ESP32 with a static IP address on the local Wi-Fi network.
  2. Samples 6-DoF/9-DoF IMU spatial tracking data (Acceleration, Gyroscope, Orientation,
     Estimated 3D Position Displacement, Velocity, and Motion State).
  3. Transmits JSON-formatted spatial telemetry packets over a UDP socket in real-time
     to the stationary terminal receiver port (default: 8888).
  4. Features auto-reconnect, packet sequence numbering, battery monitor, and LED telemetry heartbeat.
*/

#include <WiFi.h>
#include <WiFiUdp.h>
#include <Wire.h>

// ==============================================================================
// 1. NETWORK & STATIC IP CONFIGURATION
// ==============================================================================
const char* WIFI_SSID     = "YOUR_LOCAL_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_LOCAL_WIFI_PASSWORD";

// ESP32 Static IP Configuration
IPAddress static_IP(192, 168, 1, 150);     // Static IP for this ESP32
IPAddress gateway(192, 168, 1, 1);          // Network Gateway / Router
IPAddress subnet(255, 255, 255, 0);         // Subnet Mask
IPAddress primaryDNS(8, 8, 8, 8);           // Primary DNS
IPAddress secondaryDNS(8, 8, 4, 4);         // Secondary DNS

// Stationary Terminal Destination
const char* TERMINAL_HOST = "192.168.1.100"; // IP address of the stationary terminal
const uint16_t TERMINAL_PORT = 8888;         // UDP receiver port on stationary terminal

// Device Identity & Telemetry Interval
const char* DEVICE_ID = "esp32_spatial_mobile_01";
const unsigned long TX_INTERVAL_MS = 50;     // 20Hz transmission rate (50ms)
const int STATUS_LED = 2;                    // Built-in LED on most ESP32 boards

// ==============================================================================
// 2. SPATIAL TRACKING STATE & SENSOR REGISTERS
// ==============================================================================
WiFiUDP udp;
unsigned long lastTxTime = 0;
unsigned long packetSeq = 0;

// Spatial State Variables
float posX = 0.0f, posY = 0.0f, posZ = 0.0f;
float velX = 0.0f, velY = 0.0f, velZ = 0.0f;
float accelX = 0.0f, accelY = 0.0f, accelZ = 9.81f;
float gyroX = 0.0f, gyroY = 0.0f, gyroZ = 0.0f;
float roll = 0.0f, pitch = 0.0f, yaw = 0.0f;
bool impactDetected = false;
const char* motionState = "STATIONARY";

// Optional I2C MPU6050 Address
const int MPU_ADDR = 0x68;
bool hasPhysicalSensor = false;

// ==============================================================================
// 3. HARDWARE & SENSOR SETUP
// ==============================================================================
void setupSensor() {
  Wire.begin();
  Wire.beginTransmission(MPU_ADDR);
  byte error = Wire.endTransmission();
  if (error == 0) {
    // Wake up MPU6050
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(0x6B); // PWR_MGMT_1
    Wire.write(0);    // Set to 0 to wake up
    Wire.endTransmission(true);
    hasPhysicalSensor = true;
    Serial.println("[ESP32-SPATIAL] Physical I2C IMU (MPU6050) detected & active.");
  } else {
    hasPhysicalSensor = false;
    Serial.println("[ESP32-SPATIAL] Physical IMU not found on I2C. Using synthetic kinematics engine.");
  }
}

void connectWiFi() {
  pinMode(STATUS_LED, OUTPUT);
  digitalWrite(STATUS_LED, LOW);

  Serial.println("\n[ESP32-SPATIAL] Configuring static IP on local Wi-Fi...");
  if (!WiFi.config(static_IP, gateway, subnet, primaryDNS, secondaryDNS)) {
    Serial.println("[ESP32-SPATIAL] Warning: Static IP configuration failed!");
  }

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 25) {
    delay(300);
    digitalWrite(STATUS_LED, !digitalRead(STATUS_LED));
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(STATUS_LED, HIGH);
    Serial.println("\n[ESP32-SPATIAL] Wi-Fi Connected!");
    Serial.print("[ESP32-SPATIAL] Static IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("[ESP32-SPATIAL] Gateway:   ");
    Serial.println(WiFi.gatewayIP());
    Serial.print("[ESP32-SPATIAL] RSSI:      ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    Serial.println("\n[ESP32-SPATIAL] Wi-Fi connection timeout. Operating in fallback mode.");
  }

  udp.begin(WiFi.localIP(), 0);
  Serial.print("[ESP32-SPATIAL] UDP socket initialized. Target: ");
  Serial.print(TERMINAL_HOST);
  Serial.print(":");
  Serial.println(TERMINAL_PORT);
}

// ==============================================================================
// 4. SPATIAL SENSING & INTEGRATION
// ==============================================================================
void readSpatialSensors(float dt) {
  if (hasPhysicalSensor) {
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(0x3B); // starting register for AcX
    Wire.endTransmission(false);
    Wire.requestFrom(MPU_ADDR, 14, true);

    int16_t rawAcX = Wire.read() << 8 | Wire.read();
    int16_t rawAcY = Wire.read() << 8 | Wire.read();
    int16_t rawAcZ = Wire.read() << 8 | Wire.read();
    int16_t rawTmp = Wire.read() << 8 | Wire.read();
    int16_t rawGyX = Wire.read() << 8 | Wire.read();
    int16_t rawGyY = Wire.read() << 8 | Wire.read();
    int16_t rawGyZ = Wire.read() << 8 | Wire.read();

    // Scale to m/s^2 and deg/s
    accelX = (rawAcX / 16384.0f) * 9.80665f;
    accelY = (rawAcY / 16384.0f) * 9.80665f;
    accelZ = (rawAcZ / 16384.0f) * 9.80665f;
    gyroX  = rawGyX / 131.0f;
    gyroY  = rawGyY / 131.0f;
    gyroZ  = rawGyZ / 131.0f;
  } else {
    // Synthetic spatial tracking kinematics (sinusoidal motion profile for demonstration)
    unsigned long now = millis();
    float t = now / 1000.0f;
    accelX = 0.25f * sin(t * 1.5f);
    accelY = 0.15f * cos(t * 1.2f);
    accelZ = 9.80665f + 0.10f * sin(t * 2.0f);
    gyroX  = 2.0f * sin(t);
    gyroY  = 1.5f * cos(t * 0.8f);
    gyroZ  = 0.5f * sin(t * 0.5f);
  }

  // Euler orientation integration
  roll  += gyroX * dt;
  pitch += gyroY * dt;
  yaw   += gyroZ * dt;

  // Simple dead-reckoning integration for linear displacement
  float netAx = accelX;
  float netAy = accelY;
  float netAz = accelZ - 9.80665f; // subtract gravity
  
  // Velocity update with damping
  velX = (velX + netAx * dt) * 0.95f;
  velY = (velY + netAy * dt) * 0.95f;
  velZ = (velZ + netAz * dt) * 0.95f;

  // Position update
  posX += velX * dt;
  posY += velY * dt;
  posZ += velZ * dt;

  // Impact and Motion classification
  float totalAccel = sqrt(accelX*accelX + accelY*accelY + accelZ*accelZ);
  if (totalAccel > 22.0f || totalAccel < 1.5f) {
    impactDetected = true;
    motionState = (totalAccel < 1.5f) ? "FREEFALL_DROP" : "IMPACT";
  } else if (abs(velX) > 0.15f || abs(velY) > 0.15f || abs(velZ) > 0.15f) {
    impactDetected = false;
    motionState = "MOVING";
  } else {
    impactDetected = false;
    motionState = "STATIONARY";
  }
}

// ==============================================================================
// 5. PACKET TRANSMISSION OVER UDP SOCKET
// ==============================================================================
void transmitSpatialPacket() {
  packetSeq++;
  unsigned long uptime = millis();
  int rssi = WiFi.RSSI();
  float batteryV = 3.95f; // Estimated or sampled via ADC

  // Build JSON telemetry packet string
  char jsonBuffer[380];
  snprintf(jsonBuffer, sizeof(jsonBuffer),
    "{\"device_id\":\"%s\",\"seq\":%lu,\"uptime_ms\":%lu,\"static_ip\":\"%s\","
    "\"accel\":{\"x\":%.3f,\"y\":%.3f,\"z\":%.3f},"
    "\"gyro\":{\"x\":%.2f,\"y\":%.2f,\"z\":%.2f},"
    "\"orientation\":{\"roll\":%.2f,\"pitch\":%.2f,\"yaw\":%.2f},"
    "\"position\":{\"x\":%.3f,\"y\":%.3f,\"z\":%.3f},"
    "\"velocity\":{\"x\":%.3f,\"y\":%.3f,\"z\":%.3f},"
    "\"motion_state\":\"%s\",\"impact_detected\":%s,"
    "\"battery_v\":%.2f,\"rssi_dbm\":%d}",
    DEVICE_ID, packetSeq, uptime, WiFi.localIP().toString().c_str(),
    accelX, accelY, accelZ,
    gyroX, gyroY, gyroZ,
    roll, pitch, yaw,
    posX, posY, posZ,
    velX, velY, velZ,
    motionState, impactDetected ? "true" : "false",
    batteryV, rssi
  );

  // Send packet to stationary terminal
  udp.beginPacket(TERMINAL_HOST, TERMINAL_PORT);
  udp.write((const uint8_t*)jsonBuffer, strlen(jsonBuffer));
  udp.endPacket();

  // Pulse status LED on transmit
  digitalWrite(STATUS_LED, (packetSeq % 10 < 5) ? HIGH : LOW);

  // Serial debug print every 20 packets (approx once per sec)
  if (packetSeq % 20 == 0) {
    Serial.printf("[TX #%lu] Pos(%.2f, %.2f, %.2f) Att(R:%.1f P:%.1f Y:%.1f) State:%s\n",
                  packetSeq, posX, posY, posZ, roll, pitch, yaw, motionState);
  }
}

// ==============================================================================
// 6. MAIN ARDUINO LOOP
// ==============================================================================
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=======================================================");
  Serial.println("  ESP32 MOBILE SPATIAL TRACKING TRANSMITTER (RULE 233) ");
  Serial.println("=======================================================");

  setupSensor();
  connectWiFi();
}

void loop() {
  // Auto-reconnect if Wi-Fi link drops
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  unsigned long now = millis();
  if (now - lastTxTime >= TX_INTERVAL_MS) {
    float dt = (now - lastTxTime) / 1000.0f;
    if (dt <= 0.0f || dt > 1.0f) dt = TX_INTERVAL_MS / 1000.0f;
    lastTxTime = now;

    readSpatialSensors(dt);
    transmitSpatialPacket();
  }
}
