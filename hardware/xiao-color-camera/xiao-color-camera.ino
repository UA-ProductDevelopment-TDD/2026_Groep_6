// =====================================================================
//  Bittle "chameleon" floor-color camera
//  Board: Seeed Studio XIAO ESP32-S3 Sense (camera board attached)
//
//  What it does
//  - The camera looks straight DOWN at the floor under the Bittle.
//  - Every frame it averages the color in the middle of the image.
//  - It drives a strip of WS2812 / NeoPixel LEDs in that color.
//  - The measured color can be read:
//      * over USB serial:  "COLOR r g b #RRGGBB" lines (5x per second)
//      * over WiFi:        http://<ip>/color   -> JSON
//                          http://<ip>/        -> live view + color swatch
//                          http://<ip>/capture -> one JPEG snapshot
//                          http://<ip>:81/stream -> MJPEG live video
//
//  Arduino IDE settings (Tools menu)
//  - Board:  "XIAO_ESP32S3"   (esp32 by Espressif, version 3.x)
//  - PSRAM:  "OPI PSRAM"      <-- required, otherwise the camera fails
//  - Library: "Adafruit NeoPixel" (Library Manager)
//
//  WiFi: copy wifi_secrets.example.h to wifi_secrets.h and fill it in.
//  Without it, the XIAO makes its own WiFi network "Bittle-Cam".
//
//  Serial commands (115200 baud, Serial Monitor):
//    w  = white calibration: hold the dog above a WHITE sheet of paper first
//    r  = reset the calibration
//    i  = print info (IP address, calibration)
// =====================================================================

#include "esp_camera.h"
#include "esp_http_server.h"
#include "img_converters.h"
#include <WiFi.h>
#include <ESPmDNS.h>
#include <Preferences.h>
#include <Adafruit_NeoPixel.h>

#if __has_include("wifi_secrets.h")
#include "wifi_secrets.h"  // defines WIFI_SSID and WIFI_PASSWORD (not in git)
#endif
#ifndef WIFI_SSID
#define WIFI_SSID ""
#define WIFI_PASSWORD ""
#endif

// ---------------------------- settings -------------------------------
#define LED_PIN          D1    // data line of the NeoPixel strip
#define LED_COUNT        8     // number of LEDs on the strip
#define LED_BRIGHTNESS   80    // 0-255. Keep low: LEDs draw a lot of current
#define LIGHT_PIN        D3    // white LED next to the lens (lights the floor). -1 = none

#define SAMPLE_FRACTION  0.5f  // use the middle 50% of the image (edges are darker)
#define SMOOTHING        0.25f // 0..1, lower = calmer LED changes
#define SATURATION_BOOST 1.6f  // floor colors look dull on camera; make LEDs more vivid
#define DARK_LEVEL       0.06f // floor darker than this -> LEDs off
#define FULL_LEVEL       0.45f // floor brighter than this -> LEDs full brightness

#define AP_SSID          "Bittle-Cam"   // own network when no WiFi is configured
#define AP_PASSWORD      "bittle123"    // at least 8 characters
#define HOSTNAME         "bittle-cam"   // -> http://bittle-cam.local

// ------------------ XIAO ESP32-S3 Sense camera pins -------------------
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

// ----------------------------- state ----------------------------------
Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);
Preferences prefs;

float gainR = 1, gainG = 1, gainB = 1;  // white calibration
float ledR = 0, ledG = 0, ledB = 0;     // smoothed LED color (0..255)

// latest measurement, shared with the web server task
portMUX_TYPE colorMux = portMUX_INITIALIZER_UNLOCKED;
uint8_t floorR, floorG, floorB;   // calibrated floor color
uint8_t rawR, rawG, rawB;         // uncalibrated average
uint8_t outR, outG, outB;         // color sent to the LEDs
uint32_t frameCount = 0;

volatile bool calibrateRequested = false;
httpd_handle_t webServer = NULL;
httpd_handle_t streamServer = NULL;

// ---------------------------- camera ----------------------------------
bool setupCamera() {
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0;
  c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = Y2_GPIO_NUM;  c.pin_d1 = Y3_GPIO_NUM;
  c.pin_d2 = Y4_GPIO_NUM;  c.pin_d3 = Y5_GPIO_NUM;
  c.pin_d4 = Y6_GPIO_NUM;  c.pin_d5 = Y7_GPIO_NUM;
  c.pin_d6 = Y8_GPIO_NUM;  c.pin_d7 = Y9_GPIO_NUM;
  c.pin_xclk = XCLK_GPIO_NUM;
  c.pin_pclk = PCLK_GPIO_NUM;
  c.pin_vsync = VSYNC_GPIO_NUM;
  c.pin_href = HREF_GPIO_NUM;
  c.pin_sccb_sda = SIOD_GPIO_NUM;
  c.pin_sccb_scl = SIOC_GPIO_NUM;
  c.pin_pwdn = PWDN_GPIO_NUM;
  c.pin_reset = RESET_GPIO_NUM;
  c.xclk_freq_hz = 20000000;
  c.pixel_format = PIXFORMAT_RGB565;  // raw pixels: easy to average, no JPEG decoding
  c.frame_size = FRAMESIZE_QVGA;      // 320x240 is plenty for a color average
  c.fb_count = 2;
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = CAMERA_GRAB_LATEST;

  esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed (0x%x). Is PSRAM set to 'OPI PSRAM'? Is the camera board clicked on?\n", err);
    return false;
  }

  sensor_t *s = esp_camera_sensor_get();
  // Automatic white balance would "correct" a colored floor back to gray,
  // so we switch it off and use our own white calibration instead.
  s->set_whitebal(s, 0);
  s->set_awb_gain(s, 0);
  s->set_wb_mode(s, 3);        // fixed "office" white balance
  s->set_exposure_ctrl(s, 1);  // auto exposure stays on (we normalise brightness)
  s->set_gain_ctrl(s, 1);
  s->set_saturation(s, 1);
  return true;
}

// Average the middle part of an RGB565 frame. Pixels are stored high byte first.
void averageColor(camera_fb_t *fb, float &r, float &g, float &b) {
  int w = fb->width, h = fb->height;
  int x0 = w * (1 - SAMPLE_FRACTION) / 2, x1 = w - x0;
  int y0 = h * (1 - SAMPLE_FRACTION) / 2, y1 = h - y0;
  uint32_t sr = 0, sg = 0, sb = 0, n = 0;
  for (int y = y0; y < y1; y += 2) {
    const uint8_t *row = fb->buf + (size_t)y * w * 2;
    for (int x = x0; x < x1; x += 2) {
      uint8_t hb = row[x * 2], lb = row[x * 2 + 1];
      sr += hb & 0xF8;
      sg += ((hb & 0x07) << 5) | ((lb & 0xE0) >> 3);
      sb += (lb & 0x1F) << 3;
      n++;
    }
  }
  r = (float)sr / n;
  g = (float)sg / n;
  b = (float)sb / n;
}

// ------------------------- calibration --------------------------------
void loadCalibration() {
  prefs.begin("colorcam", true);
  gainR = prefs.getFloat("gr", 1);
  gainG = prefs.getFloat("gg", 1);
  gainB = prefs.getFloat("gb", 1);
  prefs.end();
}

void saveCalibration() {
  prefs.begin("colorcam", false);
  prefs.putFloat("gr", gainR);
  prefs.putFloat("gg", gainG);
  prefs.putFloat("gb", gainB);
  prefs.end();
}

void calibrateWhite(float r, float g, float b) {
  float m = max(r, max(g, b));
  if (m < 20) {
    Serial.println("Calibration failed: image too dark. Is the white LED on?");
    return;
  }
  gainR = m / max(r, 1.0f);
  gainG = m / max(g, 1.0f);
  gainB = m / max(b, 1.0f);
  saveCalibration();
  Serial.printf("White calibration saved: gains R=%.2f G=%.2f B=%.2f\n", gainR, gainG, gainB);
}

// ------------------------ color -> LED color --------------------------
void rgbToHsv(float r, float g, float b, float &h, float &s, float &v) {
  float mx = max(r, max(g, b)), mn = min(r, min(g, b)), d = mx - mn;
  v = mx;
  s = mx > 0 ? d / mx : 0;
  if (d == 0) h = 0;
  else if (mx == r) h = fmodf((g - b) / d + 6, 6);
  else if (mx == g) h = (b - r) / d + 2;
  else h = (r - g) / d + 4;
  h *= 60;
}

void hsvToRgb(float h, float s, float v, float &r, float &g, float &b) {
  float c = v * s, x = c * (1 - fabsf(fmodf(h / 60, 2) - 1)), m = v - c;
  float rr = 0, gg = 0, bb = 0;
  if (h < 60) { rr = c; gg = x; }
  else if (h < 120) { rr = x; gg = c; }
  else if (h < 180) { gg = c; bb = x; }
  else if (h < 240) { gg = x; bb = c; }
  else if (h < 300) { rr = x; bb = c; }
  else { rr = c; bb = x; }
  r = rr + m; g = gg + m; b = bb + m;
}

// Floor color (0..255) -> LED color (0..255): brighter and more vivid.
void floorToLed(float r, float g, float b, float &lr, float &lg, float &lb) {
  float h, s, v;
  rgbToHsv(r / 255, g / 255, b / 255, h, s, v);
  s = min(1.0f, s * SATURATION_BOOST);
  v = constrain((v - DARK_LEVEL) / (FULL_LEVEL - DARK_LEVEL), 0.0f, 1.0f);
  hsvToRgb(h, s, v, lr, lg, lb);
  lr *= 255; lg *= 255; lb *= 255;
}

void showLeds(uint8_t r, uint8_t g, uint8_t b) {
  uint32_t c = strip.gamma32(strip.Color(r, g, b));
  for (int i = 0; i < LED_COUNT; i++) strip.setPixelColor(i, c);
  strip.show();
}

// --------------------------- web server -------------------------------
static const char INDEX_HTML[] = R"HTML(<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bittle Cam</title>
<style>body{font-family:sans-serif;margin:16px;background:#111;color:#eee}
img{width:100%;max-width:480px;border-radius:8px;display:block}
#sw{width:100%;max-width:480px;height:80px;border-radius:8px;margin:12px 0}
button{font-size:16px;padding:8px 14px}</style></head><body>
<h2>Bittle floor camera</h2>
<img id="cam" alt="camera">
<div id="sw"></div><p id="txt">...</p>
<button onclick="fetch('/calibrate').then(r=>r.text()).then(t=>alert(t))">White calibration</button>
<p><small>Hold the dog above a white sheet of paper before calibrating.</small></p>
<script>
document.getElementById('cam').src='http://'+location.hostname+':81/stream';
setInterval(()=>fetch('/color').then(r=>r.json()).then(c=>{
 document.getElementById('sw').style.background=c.led_hex;
 document.getElementById('txt').textContent='floor '+c.hex+'  ->  LEDs '+c.led_hex;
}).catch(()=>{}),300);
</script></body></html>)HTML";

esp_err_t indexHandler(httpd_req_t *req) {
  httpd_resp_set_type(req, "text/html");
  return httpd_resp_send(req, INDEX_HTML, HTTPD_RESP_USE_STRLEN);
}

esp_err_t colorHandler(httpd_req_t *req) {
  uint8_t fr, fg, fb, lr, lg, lb, rr, rg, rb;
  uint32_t n;
  portENTER_CRITICAL(&colorMux);
  fr = floorR; fg = floorG; fb = floorB;
  lr = outR; lg = outG; lb = outB;
  rr = rawR; rg = rawG; rb = rawB;
  n = frameCount;
  portEXIT_CRITICAL(&colorMux);
  char json[220];
  snprintf(json, sizeof(json),
           "{\"r\":%u,\"g\":%u,\"b\":%u,\"hex\":\"#%02X%02X%02X\","
           "\"led\":[%u,%u,%u],\"led_hex\":\"#%02X%02X%02X\",\"raw\":[%u,%u,%u],\"frame\":%lu}",
           fr, fg, fb, fr, fg, fb, lr, lg, lb, lr, lg, lb, rr, rg, rb, (unsigned long)n);
  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");  // so the game page can read it too
  return httpd_resp_send(req, json, HTTPD_RESP_USE_STRLEN);
}

esp_err_t calibrateHandler(httpd_req_t *req) {
  calibrateRequested = true;
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  return httpd_resp_send(req, "White calibration done (see Serial Monitor for gains).", HTTPD_RESP_USE_STRLEN);
}

esp_err_t captureHandler(httpd_req_t *req) {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) return httpd_resp_send_500(req);
  uint8_t *jpg = NULL;
  size_t len = 0;
  bool ok = frame2jpg(fb, 80, &jpg, &len);
  esp_camera_fb_return(fb);
  if (!ok) return httpd_resp_send_500(req);
  httpd_resp_set_type(req, "image/jpeg");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  esp_err_t res = httpd_resp_send(req, (const char *)jpg, len);
  free(jpg);
  return res;
}

#define PART_BOUNDARY "bittleframe"
esp_err_t streamHandler(httpd_req_t *req) {
  httpd_resp_set_type(req, "multipart/x-mixed-replace;boundary=" PART_BOUNDARY);
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  char head[80];
  while (true) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) return ESP_FAIL;
    uint8_t *jpg = NULL;
    size_t len = 0;
    bool ok = frame2jpg(fb, 60, &jpg, &len);
    esp_camera_fb_return(fb);
    if (!ok) return ESP_FAIL;
    int hl = snprintf(head, sizeof(head),
                      "\r\n--" PART_BOUNDARY "\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n",
                      (unsigned)len);
    esp_err_t res = httpd_resp_send_chunk(req, head, hl);
    if (res == ESP_OK) res = httpd_resp_send_chunk(req, (const char *)jpg, len);
    free(jpg);
    if (res != ESP_OK) return res;  // browser closed the stream
    vTaskDelay(pdMS_TO_TICKS(50));
  }
}

void startWebServer() {
  httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
  cfg.server_port = 80;
  httpd_uri_t pages[] = {
      {"/", HTTP_GET, indexHandler, NULL},
      {"/color", HTTP_GET, colorHandler, NULL},
      {"/calibrate", HTTP_GET, calibrateHandler, NULL},
      {"/capture", HTTP_GET, captureHandler, NULL},
  };
  if (httpd_start(&webServer, &cfg) == ESP_OK)
    for (auto &p : pages) httpd_register_uri_handler(webServer, &p);

  cfg.server_port = 81;  // stream on its own server so it doesn't block /color
  cfg.ctrl_port += 1;
  httpd_uri_t stream = {"/stream", HTTP_GET, streamHandler, NULL};
  if (httpd_start(&streamServer, &cfg) == ESP_OK)
    httpd_register_uri_handler(streamServer, &stream);
}

void startWiFi() {
  WiFi.setHostname(HOSTNAME);
  if (strlen(WIFI_SSID) > 0) {
    Serial.printf("Connecting to WiFi \"%s\"", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    for (int i = 0; i < 30 && WiFi.status() != WL_CONNECTED; i++) {
      delay(500);
      Serial.print('.');
    }
    Serial.println();
  }
  if (WiFi.status() == WL_CONNECTED) {
    WiFi.setSleep(false);  // smoother video
    Serial.printf("WiFi connected. Open http://%s/  (or http://%s.local/)\n",
                  WiFi.localIP().toString().c_str(), HOSTNAME);
  } else {
    WiFi.mode(WIFI_AP);
    WiFi.softAP(AP_SSID, AP_PASSWORD);
    Serial.printf("Own WiFi \"%s\" (password %s). Open http://%s/\n", AP_SSID, AP_PASSWORD,
                  WiFi.softAPIP().toString().c_str());
  }
  MDNS.begin(HOSTNAME);
}

void printInfo() {
  IPAddress ip = WiFi.status() == WL_CONNECTED ? WiFi.localIP() : WiFi.softAPIP();
  Serial.printf("IP: %s   gains R=%.2f G=%.2f B=%.2f   frames: %lu\n", ip.toString().c_str(), gainR, gainG,
                gainB, (unsigned long)frameCount);
}

// ------------------------------ main ----------------------------------
bool cameraOk = false;

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\nBittle floor-color camera");

  strip.begin();
  strip.setBrightness(LED_BRIGHTNESS);
  showLeds(0, 0, 0);

  if (LIGHT_PIN >= 0) {
    pinMode(LIGHT_PIN, OUTPUT);
    digitalWrite(LIGHT_PIN, HIGH);  // light up the floor under the camera
  }

  loadCalibration();
  cameraOk = setupCamera();
  if (!cameraOk) {
    showLeds(255, 0, 0);  // red = camera problem
    return;
  }
  startWiFi();
  startWebServer();
  printInfo();
}

void loop() {
  if (!cameraOk) {
    delay(1000);
    return;
  }

  // serial commands
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 'w') calibrateRequested = true;
    else if (c == 'r') {
      gainR = gainG = gainB = 1;
      saveCalibration();
      Serial.println("Calibration reset.");
    } else if (c == 'i') printInfo();
  }

  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    delay(10);
    return;
  }
  float r, g, b;
  averageColor(fb, r, g, b);
  esp_camera_fb_return(fb);

  if (calibrateRequested) {
    calibrateRequested = false;
    calibrateWhite(r, g, b);
  }

  // calibrated floor color
  float cr = min(255.0f, r * gainR), cg = min(255.0f, g * gainG), cb = min(255.0f, b * gainB);

  // LED color, smoothed so it doesn't flicker
  float lr, lg, lb;
  floorToLed(cr, cg, cb, lr, lg, lb);
  ledR += (lr - ledR) * SMOOTHING;
  ledG += (lg - ledG) * SMOOTHING;
  ledB += (lb - ledB) * SMOOTHING;
  showLeds(ledR, ledG, ledB);

  portENTER_CRITICAL(&colorMux);
  rawR = r; rawG = g; rawB = b;
  floorR = cr; floorG = cg; floorB = cb;
  outR = ledR; outG = ledG; outB = ledB;
  frameCount++;
  portEXIT_CRITICAL(&colorMux);

  static uint32_t lastPrint = 0;
  if (millis() - lastPrint >= 200) {
    lastPrint = millis();
    Serial.printf("COLOR %u %u %u #%02X%02X%02X\n", (unsigned)cr, (unsigned)cg, (unsigned)cb, (unsigned)cr,
                  (unsigned)cg, (unsigned)cb);
  }
}
