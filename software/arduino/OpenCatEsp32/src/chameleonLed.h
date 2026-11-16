// Chameleon LEDs: a NeoPixel (WS2812B) strip on the Bittle whose colour is set over serial.
// Turned on with "#define CHAMELEON_LED" in OpenCatEsp32.ino. Without that define, none of this is compiled.
//
// Serial Monitor (115200 baud, line ending "Newline"):
//   v 255 0 0      set the colour as R G B (0-255)
//   v 255 0 0 40   same, plus the strip's separate white LED (RGBW strip, 0-255)
//   v #00FF00      set the colour as hex
//   v blue         colour by name: red orange yellow green cyan blue purple pink white
//   v off          LEDs off (a bare "v" does the same)
//   v pin 9        move the strip to another GPIO and light it white, to find where it is connected
//   v count 8      change the number of LEDs
//   v ?            print the current pin, count and colour
//
// Later the camera can send exactly the same "v r g b" lines.

#include "Adafruit_NeoPixel/Adafruit_NeoPixel.h"

#ifndef CHAMELEON_LED_PIN
#define CHAMELEON_LED_PIN 10  // GPIO wired to the strip's DIN. Grove UART2 on BiBoard V1 = GPIO 9 and 10.
#endif
#ifndef CHAMELEON_LED_COUNT
#define CHAMELEON_LED_COUNT 8
#endif
#ifndef CHAMELEON_LED_BRIGHTNESS
#define CHAMELEON_LED_BRIGHTNESS 80  // 0-255. Keep it low: a bright strip draws a lot from the robot's 5 V
#endif

#define T_CHAMELEON 'v'

Adafruit_NeoPixel chameleonStrip(CHAMELEON_LED_COUNT, CHAMELEON_LED_PIN, NEO_GRBW + NEO_KHZ800);
int chameleonPin = CHAMELEON_LED_PIN;
uint8_t chameleonRGB[4] = { 0, 0, 0, 0 };  // R, G, B and the white LED

void chameleonShow() {
  chameleonStrip.fill(chameleonStrip.Color(chameleonRGB[0], chameleonRGB[1], chameleonRGB[2], chameleonRGB[3]));
  chameleonStrip.show();
}

void chameleonSetColor(int r, int g, int b, int w = 0) {
  chameleonRGB[0] = constrain(r, 0, 255);
  chameleonRGB[1] = constrain(g, 0, 255);
  chameleonRGB[2] = constrain(b, 0, 255);
  chameleonRGB[3] = constrain(w, 0, 255);
  chameleonShow();
}

void chameleonLedSetup() {
  chameleonStrip.begin();
  chameleonStrip.setBrightness(CHAMELEON_LED_BRIGHTNESS);
  chameleonStrip.clear();
  chameleonStrip.show();
}

void chameleonPrintState() {
  char line[96];
  snprintf(line, sizeof(line), "LED pin %d, %d LEDs, colour %d %d %d #%02X%02X%02X, white %d", chameleonPin,
           chameleonStrip.numPixels(), chameleonRGB[0], chameleonRGB[1], chameleonRGB[2], chameleonRGB[0],
           chameleonRGB[1], chameleonRGB[2], chameleonRGB[3]);
  printToAllPorts(line);
}

// Pins that must not drive the strip: servo outputs, the board LED, the I2C bus of the IMU,
// the SPI flash (6-8, 11) and the input-only pins (34-39). GPIO 9 and 10 are free on BiBoard V1 (Grove UART2).
bool chameleonPinAllowed(int pin) {
  if (pin < 0 || pin > 33 || (pin >= 6 && pin <= 8) || pin == 11 || pin == 21 || pin == 22)
    return false;
  for (int i = 0; i < PWM_NUM; i++)
    if (PWM_pin[i] == pin)
      return false;
#ifdef PWM_LED_PIN
  if (pin == PWM_LED_PIN)
    return false;
#endif
#ifdef BUZZER
  if (pin == BUZZER)
    return false;
#endif
  return true;
}

struct ChameleonNamedColor {
  const char *name;
  uint8_t r, g, b;
};
const ChameleonNamedColor chameleonNames[] = {
  { "red", 255, 0, 0 },     { "orange", 255, 80, 0 }, { "yellow", 255, 200, 0 },  { "green", 0, 255, 0 },
  { "cyan", 0, 255, 255 },  { "blue", 0, 0, 255 },    { "purple", 140, 0, 255 },  { "pink", 255, 40, 120 },
  { "white", 255, 255, 255 }, { "off", 0, 0, 0 },     { "black", 0, 0, 0 },
};

void chameleonCommand(const char *cmd) {
  while (*cmd == ' ')
    cmd++;
  int a, b, c, d = 0;  // d = white LED, stays 0 for "v r g b"
  if (*cmd == '\0') {
    chameleonSetColor(0, 0, 0);
  } else if (*cmd == '?') {
    // only print
  } else if (!strncmp(cmd, "pin", 3)) {
    if (sscanf(cmd + 3, "%d", &a) != 1 || !chameleonPinAllowed(a)) {
      printToAllPorts("This pin can't drive the LEDs (servo, flash, I2C or input-only pin). Try 10 or 9 (Grove UART2).");
      return;
    }
    chameleonStrip.clear();
    chameleonStrip.show();     // turn the strip off on the old pin first
    chameleonStrip.setPin(a);  // also makes the new pin an output
    chameleonPin = a;
    chameleonSetColor(255, 255, 255);
  } else if (!strncmp(cmd, "count", 5)) {
    if (sscanf(cmd + 5, "%d", &a) != 1 || a < 1 || a > 300) {
      printToAllPorts("Use: v count 8");
      return;
    }
    chameleonStrip.clear();
    chameleonStrip.show();
    chameleonStrip.updateLength(a);
    chameleonShow();
  } else if (*cmd == '#') {
    unsigned long hex = strtoul(cmd + 1, NULL, 16);
    chameleonSetColor((hex >> 16) & 0xFF, (hex >> 8) & 0xFF, hex & 0xFF);
  } else if (sscanf(cmd, "%d %d %d %d", &a, &b, &c, &d) >= 3) {
    chameleonSetColor(a, b, c, d);
  } else {
    bool found = false;
    for (const ChameleonNamedColor &n : chameleonNames)
      if (!strcasecmp(cmd, n.name)) {
        chameleonSetColor(n.r, n.g, n.b);
        found = true;
        break;
      }
    if (!found) {
      printToAllPorts("Use: v 255 0 0, v 255 0 0 40 (RGBW), v #FF0000, v red, v off, v pin 9, v count 8 or v ?");
      return;
    }
  }
  chameleonPrintState();
}
