#include "secrets.h"
#include <Wire.h>
#include <WiFi.h>

#if MQTT_USE_SSL
  #include <WiFiClientSecure.h>
  WiFiClientSecure espClient;
#else
  WiFiClient espClient;
#endif

#include <PubSubClient.h>
#include <LiquidCrystal_I2C.h>
#include <ESP32Servo.h>

const int TRIG_PIN   = 5;
const int ECHO_PIN   = 18;  
const int RAIN_PIN   = 34;  
const int SERVO_PIN  = 13;  
const int RELAY_PIN  = 4;   
const int BUZZER_PIN = 2;   
const int LED_PIN    = 15;  
const int SDA_PIN    = 21;  
const int SCL_PIN    = 22;  

const float ALERT_DISTANCE_CM  = 100.0; 
const float DANGER_DISTANCE_CM = 60.0;  
const int RAIN_ALERT_ADC       = 2048;  
const int RAIN_DANGER_ADC      = 3276;  

const int RELAY_ON  = LOW;
const int RELAY_OFF = HIGH;
const unsigned long PUBLISH_INTERVAL_MS = 3000; 

LiquidCrystal_I2C lcd(0x27, 16, 2);
Servo gateServo;
PubSubClient mqtt(espClient);
unsigned long lastPublishMs = 0;

enum StatusAir { NORMAL, SIAGA, BAHAYA };

float readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(3);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  unsigned long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  if (duration == 0) return -1.0;
  return duration / 58.0;
}

StatusAir determineStatus(float distanceCm, int rainAdc) {
  if (distanceCm < 0 || distanceCm <= DANGER_DISTANCE_CM || rainAdc >= RAIN_DANGER_ADC) {
    return BAHAYA;
  }
  if (distanceCm <= ALERT_DISTANCE_CM || rainAdc >= RAIN_ALERT_ADC) {
    return SIAGA;
  }
  return NORMAL;
}

const char* statusText(StatusAir status) {
  switch (status) {
    case SIAGA:  return "SIAGA";
    case BAHAYA: return "BAHAYA";
    default:     return "NORMAL";
  }
}

int servoAngle(StatusAir status) {
  if (status == BAHAYA) return 90; 
  if (status == SIAGA)  return 45; 
  return 0;                        
}

void applyOutputs(StatusAir status) {
  gateServo.write(servoAngle(status));

  digitalWrite(RELAY_PIN, status == BAHAYA ? RELAY_ON : RELAY_OFF);

  digitalWrite(LED_PIN, status == NORMAL ? LOW : HIGH);

  if (status == BAHAYA) {
    tone(BUZZER_PIN, 2000);
  } else {
    noTone(BUZZER_PIN);
  }
}

void showStatus(float distanceCm, int rainAdc, StatusAir status) {
  lcd.clear();
  lcd.setCursor(0, 0);
  if (distanceCm < 0) {
    lcd.print("Air: SENSOR ERR");
  } else {
    lcd.print("Air:");
    lcd.print(distanceCm, 0);
    lcd.print("cm H:");
    lcd.print(map(rainAdc, 0, 4095, 0, 100));
    lcd.print('%');
  }
  lcd.setCursor(0, 1);
  lcd.print("Status: ");
  lcd.print(statusText(status));
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.print("Menghubungkan ke Wi-Fi (");
  Serial.print(WIFI_SSID);
  Serial.print(")");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print('.');
    attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print(" Terhubung! IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println(" Gagal terhubung ke Wi-Fi.");
  }
}

void connectMqtt() {
  while (!mqtt.connected()) {
    if (WiFi.status() != WL_CONNECTED) {
      connectWiFi();
    }
    String clientId = "esp32-floodgate-" + String((uint32_t)ESP.getEfuseMac(), HEX);
    Serial.print("Menghubungkan ke HiveMQ (");
    Serial.print(MQTT_HOST);
    Serial.print(")...");

    bool connected = false;
    if (strlen(MQTT_USERNAME) > 0) {
      connected = mqtt.connect(clientId.c_str(), MQTT_USERNAME, MQTT_PASSWORD);
    } else {
      connected = mqtt.connect(clientId.c_str());
    }

    if (connected) {
      Serial.println(" Berhasil terhubung ke broker HiveMQ!");
    } else {
      Serial.print(" Gagal, state=");
      Serial.print(mqtt.state());
      Serial.println(". Coba lagi dalam 3 detik...");
      delay(3000);
    }
  }
}

void publishReading(float distanceCm, int rainAdc, StatusAir status) {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  if (!mqtt.connected()) connectMqtt();
  mqtt.loop();

  char payload[256];
  int rainPercent = map(rainAdc, 0, 4095, 0, 100);
  if (distanceCm < 0) {
    snprintf(payload, sizeof(payload),
      "{\"jarak_cm\":null,\"hujan_adc\":%d,\"hujan_persen\":%d,\"status\":\"%s\",\"servo_derajat\":%d,\"pompa\":%s}",
      rainAdc, rainPercent, statusText(status), servoAngle(status), status == BAHAYA ? "true" : "false");
  } else {
    snprintf(payload, sizeof(payload),
      "{\"jarak_cm\":%.1f,\"hujan_adc\":%d,\"hujan_persen\":%d,\"status\":\"%s\",\"servo_derajat\":%d,\"pompa\":%s}",
      distanceCm, rainAdc, rainPercent, statusText(status), servoAngle(status), status == BAHAYA ? "true" : "false");
  }

  if (mqtt.publish(MQTT_TOPIC, payload)) {
    Serial.print("HiveMQ Publish [");
    Serial.print(MQTT_TOPIC);
    Serial.print("]: ");
    Serial.println(payload);
  } else {
    Serial.println("Gagal publish ke HiveMQ");
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("\n=== SMART FLOOD WATERGATE SYSTEM ===");

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(RAIN_PIN, INPUT);
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, RELAY_OFF);

  analogReadResolution(12);
  gateServo.setPeriodHertz(50);
  gateServo.attach(SERVO_PIN, 500, 2400);

  Wire.begin(SDA_PIN, SCL_PIN);
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("WaterGate System");
  lcd.setCursor(0, 1);
  lcd.print("Inisialisasi...");

#if MQTT_USE_SSL
  espClient.setInsecure();
#endif

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(512);

  connectWiFi();
  delay(1000);
}

void loop() {
  float distanceCm = readDistanceCm();
  int rainAdc = analogRead(RAIN_PIN);
  StatusAir status = determineStatus(distanceCm, rainAdc);

  applyOutputs(status);
  showStatus(distanceCm, rainAdc, status);

  Serial.print("Status: ");
  Serial.print(statusText(status));
  Serial.print(" | Jarak: ");
  if (distanceCm < 0) Serial.print("ERR");
  else Serial.print(distanceCm, 1);
  Serial.print(" cm | Hujan: ");
  Serial.print(map(rainAdc, 0, 4095, 0, 100));
  Serial.print("% | Servo: ");
  Serial.print(servoAngle(status));
  Serial.print(" deg | Pompa: ");
  Serial.println(status == BAHAYA ? "ON" : "OFF");

  mqtt.loop();
  if (millis() - lastPublishMs >= PUBLISH_INTERVAL_MS) {
    lastPublishMs = millis();
    publishReading(distanceCm, rainAdc, status);
  }
  delay(500);
}
