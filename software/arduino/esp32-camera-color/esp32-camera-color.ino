/*
  esp32-camera-color.ino
  ----------------------
  Reads the colour in front of an ESP32 camera module and prints it on the
  Serial Monitor (115200 baud), e.g.

      COLOR 200 40 30 #C8281E red

  Supported boards (pick one in the BOARD SELECTION block below):
    - Seeed Studio XIAO ESP32-S3 Sense   (Tools > Board: "XIAO_ESP32S3", PSRAM: "OPI PSRAM")
    - AI-Thinker ESP32-CAM               (Tools > Board: "AI Thinker ESP32-CAM")

  Needs: Arduino IDE + "esp32 by Espressif Systems" (Boards Manager, 2.x or 3.x).
  The camera driver (esp_camera.h) comes with that package; no extra libraries.

  Serial commands (type in the Serial Monitor, then Enter):
    w  white calibration: point the camera at a white sheet of paper first
    r  reset the calibration
    i  print info

  Automatic white balance is turned OFF on purpose: otherwise the camera
  "corrects" a coloured surface back towards grey. Do a white calibration once
  instead; it is stored in flash and survives a restart.
*/

#include "esp_camera.h"
#include <Preferences.h>

// ======================= BOARD SELECTION =======================
// Uncomment exactly ONE line.
#define BOARD_XIAO_ESP32S3_SENSE
// #define BOARD_AI_THINKER_ESP32CAM
// ===============================================================

// ======================= SETTINGS ==============================
const float SAMPLE_FRACTION = 0.5;   // average the middle part of the image (0.5 = middle half)
const float SMOOTHING       = 0.35;  // 0..1, lower = calmer, slower colour changes
const uint32_t PRINT_EVERY_MS = 200; // how often a COLOR line is printed
const bool USE_FLASH_LED    = false; // ESP32-CAM only: light the scene with the on-board flash LED
// ===============================================================

#if defined(BOARD_XIAO_ESP32S3_SENSE)
  #define PWDN_GPIO_NUM  -1
  #define RESET_GPIO_NUM -1
  #define XCLK_GPIO_NUM  10
  #define SIOD_GPIO_NUM  40
  #define SIOC_GPIO_NUM  39
  #define Y9_GPIO_NUM    48
  #define Y8_GPIO_NUM    11
  #define Y7_GPIO_NUM    12
  #define Y6_GPIO_NUM    14
  #define Y5_GPIO_NUM    16
  #define Y4_GPIO_NUM    18
  #define Y3_GPIO_NUM    17
  #define Y2_GPIO_NUM    15
  #define VSYNC_GPIO_NUM 38
  #define HREF_GPIO_NUM  47
  #define PCLK_GPIO_NUM  13
  #define STATUS_LED_PIN 21   // user LED, on when LOW
  #define FLASH_LED_PIN  -1
#elif defined(BOARD_AI_THINKER_ESP32CAM)
  #define PWDN_GPIO_NUM  32
  #define RESET_GPIO_NUM -1
  #define XCLK_GPIO_NUM   0
  #define SIOD_GPIO_NUM  26
  #define SIOC_GPIO_NUM  27
  #define Y9_GPIO_NUM    35
  #define Y8_GPIO_NUM    34
  #define Y7_GPIO_NUM    39
  #define Y6_GPIO_NUM    36
  #define Y5_GPIO_NUM    21
  #define Y4_GPIO_NUM    19
  #define Y3_GPIO_NUM    18
  #define Y2_GPIO_NUM     5
  #define VSYNC_GPIO_NUM 25
  #define HREF_GPIO_NUM  23
  #define PCLK_GPIO_NUM  22
  #define STATUS_LED_PIN 33   // small red LED on the back, on when LOW
  #define FLASH_LED_PIN   4   // the bright white flash LED
#else
  #error "Select a board in the BOARD SELECTION block"
#endif

Preferences prefs;
float gainR = 1.0, gainG = 1.0, gainB = 1.0;   // white calibration
float smoothR = 0, smoothG = 0, smoothB = 0;   // smoothed, calibrated colour
float rawR = 0, rawG = 0, rawB = 0;            // last raw average (for calibration)
bool haveColor = false;
uint32_t lastPrint = 0, frames = 0;

bool startCamera() {
  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk  = XCLK_GPIO_NUM;
  config.pin_pclk  = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href  = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn  = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_RGB565;   // raw colour pixels, no JPEG decoding needed
  config.frame_size   = FRAMESIZE_QQVGA;    // 160 x 120 is plenty for an average colour
  config.jpeg_quality = 12;
  if (psramFound()) {
    config.fb_location = CAMERA_FB_IN_PSRAM;
    config.fb_count    = 2;
    config.grab_mode   = CAMERA_GRAB_LATEST;
  } else {
    config.fb_location = CAMERA_FB_IN_DRAM;
    config.fb_count    = 1;
    config.grab_mode   = CAMERA_GRAB_WHEN_EMPTY;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed: 0x%x\n", err);
    return false;
  }

  sensor_t *s = esp_camera_sensor_get();
  s->set_whitebal(s, 0);       // no auto white balance (we calibrate ourselves)
  s->set_awb_gain(s, 0);
  s->set_exposure_ctrl(s, 1);  // keep auto exposure, so brightness adapts
  s->set_gain_ctrl(s, 1);
  s->set_saturation(s, 2);     // a bit more vivid
  return true;
}

// Average R, G, B over the middle of the frame. Returns false if no frame.
bool readFrame(float &r, float &g, float &b) {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) return false;

  const int w = fb->width, h = fb->height;
  const int x0 = w * (1 - SAMPLE_FRACTION) / 2, x1 = w - x0;
  const int y0 = h * (1 - SAMPLE_FRACTION) / 2, y1 = h - y0;
  uint32_t sumR = 0, sumG = 0, sumB = 0, n = 0;

  for (int y = y0; y < y1; y += 2) {
    for (int x = x0; x < x1; x += 2) {
      const uint8_t *px = fb->buf + 2 * (y * w + x);
      uint16_t v = (px[0] << 8) | px[1];   // RGB565, high byte first
      sumR += ((v >> 11) & 0x1F) * 255 / 31;
      sumG += ((v >> 5)  & 0x3F) * 255 / 63;
      sumB += ( v        & 0x1F) * 255 / 31;
      n++;
    }
  }
  esp_camera_fb_return(fb);
  if (n == 0) return false;
  r = (float)sumR / n;  g = (float)sumG / n;  b = (float)sumB / n;
  return true;
}

// Rough colour name from hue / saturation / brightness.
const char *colorName(float r, float g, float b) {
  float mx = max(r, max(g, b)), mn = min(r, min(g, b)), d = mx - mn;
  float v = mx / 255.0, s = mx > 0 ? d / mx : 0;
  if (v < 0.15) return "black";
  if (s < 0.20) return v > 0.75 ? "white" : "grey";
  float h;
  if (mx == r)      h = fmod((g - b) / d + 6, 6);
  else if (mx == g) h = (b - r) / d + 2;
  else              h = (r - g) / d + 4;
  h *= 60;
  if (h < 15 || h >= 340) return "red";
  if (h < 40)  return "orange";
  if (h < 70)  return "yellow";
  if (h < 160) return "green";
  if (h < 200) return "cyan";
  if (h < 260) return "blue";
  if (h < 300) return "purple";
  return "pink";
}

void loadCalibration() {
  prefs.begin("camcolor", true);
  gainR = prefs.getFloat("gr", 1.0);
  gainG = prefs.getFloat("gg", 1.0);
  gainB = prefs.getFloat("gb", 1.0);
  prefs.end();
}

void saveCalibration() {
  prefs.begin("camcolor", false);
  prefs.putFloat("gr", gainR);
  prefs.putFloat("gg", gainG);
  prefs.putFloat("gb", gainB);
  prefs.end();
}

void whiteCalibration() {
  // Average a few fresh frames of the white sheet.
  float r = 0, g = 0, b = 0, fr, fg, fb;
  int n = 0;
  for (int i = 0; i < 10; i++) {
    if (readFrame(fr, fg, fb)) { r += fr; g += fg; b += fb; n++; }
    delay(30);
  }
  if (n == 0 || r / n < 10 || g / n < 10 || b / n < 10) {
    Serial.println("Calibration failed: image too dark. Use a white sheet and more light.");
    return;
  }
  r /= n; g /= n; b /= n;
  float target = max(r, max(g, b));   // scale every channel up to the brightest one
  gainR = target / r;  gainG = target / g;  gainB = target / b;
  saveCalibration();
  Serial.printf("White calibration saved: gains R %.2f  G %.2f  B %.2f\n", gainR, gainG, gainB);
}

void printInfo() {
#if defined(BOARD_XIAO_ESP32S3_SENSE)
  Serial.println("Board: XIAO ESP32-S3 Sense");
#else
  Serial.println("Board: AI-Thinker ESP32-CAM");
#endif
  Serial.printf("PSRAM: %s\n", psramFound() ? "yes" : "no");
  Serial.printf("White gains: R %.2f  G %.2f  B %.2f\n", gainR, gainG, gainB);
  Serial.printf("Frames read: %lu\n", (unsigned long)frames);
  Serial.println("Commands: w = white calibration, r = reset calibration, i = info");
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println("\nESP32 camera colour reader");

  if (STATUS_LED_PIN >= 0) { pinMode(STATUS_LED_PIN, OUTPUT); digitalWrite(STATUS_LED_PIN, HIGH); }
  if (FLASH_LED_PIN >= 0)  { pinMode(FLASH_LED_PIN, OUTPUT); digitalWrite(FLASH_LED_PIN, USE_FLASH_LED ? HIGH : LOW); }

  loadCalibration();
  if (!startCamera()) {
    Serial.println("Check the camera ribbon/board and (XIAO) that PSRAM is set to OPI PSRAM.");
    while (true) {   // blink fast = camera error
      if (STATUS_LED_PIN >= 0) digitalWrite(STATUS_LED_PIN, !digitalRead(STATUS_LED_PIN));
      delay(150);
    }
  }
  if (STATUS_LED_PIN >= 0) digitalWrite(STATUS_LED_PIN, LOW);   // on = running
  printInfo();
}

void loop() {
  while (Serial.available()) {
    char c = tolower(Serial.read());
    if (c == 'w') whiteCalibration();
    else if (c == 'r') { gainR = gainG = gainB = 1.0; saveCalibration(); Serial.println("Calibration reset."); }
    else if (c == 'i') printInfo();
  }

  float r, g, b;
  if (!readFrame(r, g, b)) { Serial.println("No camera frame"); delay(200); return; }
  frames++;
  rawR = r; rawG = g; rawB = b;

  r = min(255.0f, r * gainR);
  g = min(255.0f, g * gainG);
  b = min(255.0f, b * gainB);

  if (!haveColor) { smoothR = r; smoothG = g; smoothB = b; haveColor = true; }
  smoothR += SMOOTHING * (r - smoothR);
  smoothG += SMOOTHING * (g - smoothG);
  smoothB += SMOOTHING * (b - smoothB);

  if (millis() - lastPrint >= PRINT_EVERY_MS) {
    lastPrint = millis();
    int R = round(smoothR), G = round(smoothG), B = round(smoothB);
    Serial.printf("COLOR %d %d %d #%02X%02X%02X %s\n", R, G, B, R, G, B, colorName(smoothR, smoothG, smoothB));
  }
}
