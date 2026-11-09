// neopixelPinTest: checks a NeoPixel strip on the BiBoard without OpenCat.
// It lights the strip red, green, blue, white on GPIO 10, then on GPIO 9, and repeats.
// Watch the Serial Monitor (115200) to see which pin is being tried when the LEDs light up.
// Needs the "Adafruit NeoPixel" library (Library Manager). Board settings: same as OpenCatEsp32.

#include <Adafruit_NeoPixel.h>

const int PINS[] = { 10, 9 };  // Grove UART2 on BiBoard V1
const int LED_COUNT = 8;
const int BRIGHTNESS = 26;  // 10%

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("NeoPixel pin test");
}

void loop() {
  for (int pin : PINS) {
    Adafruit_NeoPixel strip(LED_COUNT, pin, NEO_GRB + NEO_KHZ800);
    strip.begin();
    strip.setBrightness(BRIGHTNESS);
    const uint32_t colors[] = { strip.Color(255, 0, 0), strip.Color(0, 255, 0), strip.Color(0, 0, 255),
                                strip.Color(255, 255, 255) };
    const char *names[] = { "red", "green", "blue", "white" };
    for (int i = 0; i < 4; i++) {
      Serial.printf("GPIO %d: %s\n", pin, names[i]);
      strip.fill(colors[i]);
      strip.show();
      delay(1000);
    }
    strip.clear();
    strip.show();
    pinMode(pin, INPUT);  // release the pin before trying the next one
    delay(500);
  }
}
