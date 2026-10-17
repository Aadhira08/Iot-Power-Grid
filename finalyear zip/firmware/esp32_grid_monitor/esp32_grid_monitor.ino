/*
 * ESP32 Grid Monitor Node
 * IoT-Based Intelligent Power Grid Fault Detection and Restoration System
 *
 * Reads (simulated or real) voltage/current of one distribution section and
 * POSTs telemetry as JSON to the Flask backend (/api/telemetry).
 *
 * Hardware (optional):
 *   - Current: SCT-013 non-invasive CT -> burden resistor -> GPIO34 (ADC)
 *   - Voltage: ZMPT101B module -> GPIO35 (ADC)
 * Without sensors the sketch runs in SIMULATION MODE and transmits synthetic
 * readings so the full IoT chain can be demonstrated.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ---------------- User configuration ----------------
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* SERVER_URL    = "http://192.168.1.100:5000/api/telemetry";
const char* DEVICE_ID     = "ESP32-NODE-01";
const char* SECTION_ID    = "SEC1";          // section monitored by this node

const uint32_t TX_INTERVAL_MS = 5000;

// ADC pins (used only when USE_REAL_SENSORS = true)
#define PIN_CURRENT 34
#define PIN_VOLTAGE 35
const bool USE_REAL_SENSORS = false;

// Sensor scaling (calibrate for your hardware!)
const float CT_RATIO      = 100.0;   // SCT-013 100A:50mA -> adjust
const float BURDEN_OHMS   = 33.0;
const float ADC_REF       = 3.3;
const int   ADC_MAX       = 4095;
const float V_SENSOR_GAIN = 220.0;   // ZMPT101B module output scaling

// Nominal section values used in simulation mode
const float NOMINAL_CURRENT_A = 50.0;
const float NOMINAL_VOLTAGE_KV = 11.0;

// ---------------- Helpers ----------------
void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("Connected. IP: ");
  Serial.println(WiFi.localIP());
}

float readCurrentSimulated() {
  // 80% of rated + noise (+ occasional harmless spike)
  float base = 0.80f * NOMINAL_CURRENT_A;
  float noise = random(-30, 31) / 10.0f;
  return base + noise;
}

float readVoltageSimulated() {
  return NOMINAL_VOLTAGE_KV * (1.0f + random(-10, 11) / 1000.0f);
}

float readCurrentReal() {
  int raw = analogRead(PIN_CURRENT);
  float v = (raw / (float)ADC_MAX) * ADC_REF;
  float iSec = (v / BURDEN_OHMS) * CT_RATIO;   // secondary->primary amps
  return iSec;
}

float readVoltageReal() {
  int raw = analogRead(PIN_VOLTAGE);
  float v = (raw / (float)ADC_MAX) * ADC_REF;
  return v * V_SENSOR_GAIN / 1000.0f;          // -> kV
}

bool postTelemetry(float v_kv, float i_a) {
  if (WiFi.status() != WL_CONNECTED) return false;

  StaticJsonDocument<256> doc;
  doc["device_id"]  = DEVICE_ID;
  doc["section_id"] = SECTION_ID;
  doc["voltage_kv"] = v_kv;
  doc["current_a"]  = i_a;
  doc["timestamp"]  = millis();
  doc["mode"]       = USE_REAL_SENSORS ? "real" : "simulated";

  String payload;
  serializeJson(doc, payload);

  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(payload);
  Serial.printf("POST %s -> HTTP %d  (%s)\n",
                SECTION_ID, code, payload.c_str());
  http.end();
  return code == 200;
}

void setup() {
  Serial.begin(115200);
  randomSeed(analogRead(0));
  if (USE_REAL_SENSORS) {
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);
  }
  connectWiFi();
  Serial.println("ESP32 Grid Monitor starting (mode: "
                 + String(USE_REAL_SENSORS ? "REAL SENSORS" : "SIMULATION") + ")");
}

void loop() {
  float v_kv = USE_REAL_SENSORS ? readVoltageReal()  : readVoltageSimulated();
  float i_a  = USE_REAL_SENSORS ? readCurrentReal()  : readCurrentSimulated();

  bool ok = postTelemetry(v_kv, i_a);
  if (!ok) {
    Serial.println("Telemetry POST failed - retrying WiFi...");
    if (WiFi.status() != WL_CONNECTED) connectWiFi();
  }
  delay(TX_INTERVAL_MS);
}
