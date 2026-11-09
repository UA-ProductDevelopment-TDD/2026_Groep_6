# Chameleon floor camera (XIAO ESP32-S3 Sense)

A Seeed Studio XIAO ESP32-S3 Sense under the Bittle looks at the floor, measures its color and lights up a NeoPixel LED strip in that color. The color can also be read by a laptop (WiFi or USB).

```
            floor color                       LED color
 floor ──> camera (XIAO ESP32-S3 Sense) ──> NeoPixel strip on the Bittle
                       │
                       ├── USB serial:  "COLOR r g b #RRGGBB"
                       └── WiFi:        /color (JSON), /capture, :81/stream, live page on /
```

The XIAO is a separate little computer with its own program. The Bittle's own firmware (BiBoard, `software/arduino`) stays as it is: the BiBoard only gives the XIAO power. Don't turn on the `XC` camera module in the Bittle firmware, that one is for other (I2C) cameras.

## Parts

| Part | Notes |
|---|---|
| Seeed XIAO ESP32-S3 **Sense** | with the camera board clicked on, and the WiFi antenna attached |
| WS2812B / NeoPixel strip, about 8 LEDs | 5 V type |
| 1 white LED + 100 Ω resistor | lights the floor under the camera (optional but recommended) |
| 330 Ω resistor | in the LED data line |
| Grove cable (or 2 jumper wires) | 5 V and GND from the BiBoard |

## Wiring

| From | To |
|---|---|
| BiBoard Grove connector **5V (red)** | XIAO **5V** pin + LED strip **5V** |
| BiBoard Grove connector **GND (black)** | XIAO **GND** + LED strip **GND** + white LED (–) |
| XIAO **D1** | 330 Ω → LED strip **DIN** |
| XIAO **D3** | 100 Ω → white LED (+) |

- Only use the red and black wires of the Grove cable. Leave the yellow and white wires (data) unconnected.
- Never connect USB to the XIAO and the BiBoard's 5 V at the same time for a long time. For programming, unplug the 5 V wire, or accept that the XIAO is powered twice only briefly.
- The LEDs draw a lot of current at full white. `LED_BRIGHTNESS` is set to 80 of 255 to keep the total low. If the Bittle resets or the servos stutter when the LEDs go bright, lower it, or give the LEDs their own 5 V supply.
- A plain WS2812 usually accepts the XIAO's 3.3 V data signal at 5 V power. If the first LED flickers or shows wrong colors, add a level shifter (e.g. 74AHCT125).

## Mounting

- Lens pointing **straight down**, about 3–6 cm above the floor. Sharp focus doesn't matter, we only need the average color.
- Under the chest or the back, wherever the battery and legs leave room. Check that no leg hits it when walking.
- Put the white LED right next to the lens.
- **Keep the colored LEDs out of the camera's view and away from the floor under it** (on the back or sides, shielded underneath). Otherwise the camera sees its own LED color, and the color keeps feeding on itself.

## Programming the XIAO

1. Arduino IDE → **Boards Manager** → install **esp32 by Espressif** (version 3.x).
2. **Library Manager** → install **Adafruit NeoPixel**.
3. Open `xiao-color-camera/xiao-color-camera.ino`.
4. **Tools** → Board: **XIAO_ESP32S3**, PSRAM: **OPI PSRAM** (the camera won't start without this).
5. WiFi (optional): copy `wifi_secrets.example.h` to `wifi_secrets.h` and fill in your hotspot name and password. This file is not uploaded to git.
6. Upload, then open the Serial Monitor at **115200** baud. You'll see the IP address and `COLOR ...` lines.

If all LEDs light up **red**, the camera didn't start: check that the camera board is clicked on and that PSRAM is set to OPI PSRAM.

## White calibration (do this once)

The camera's own automatic white balance is turned off, because it would turn a colored floor back to gray. So calibrate once:

1. Put the Bittle on a **white sheet of paper** (with the white LED on).
2. Type `w` in the Serial Monitor, or press **White calibration** on the web page.

The calibration is saved in the XIAO and survives a restart. `r` resets it, `i` prints info.

## Reading the color

| Where | How |
|---|---|
| Serial Monitor (USB) | lines like `COLOR 200 40 30 #C8281E` |
| Browser | `http://<ip>/` shows the live camera view and the color. With your own WiFi: `http://bittle-cam.local/` also works. Without WiFi setup: connect to network **Bittle-Cam** (password `bittle123`) and open `http://192.168.4.1/` |
| Any program | `http://<ip>/color` returns JSON: `{"r":200,"g":40,"b":30,"hex":"#C8281E","led":[255,51,25],"led_hex":"#FF3319","raw":[...],"frame":123}` |
| Python | `python read_color.py --url http://bittle-cam.local` or `python read_color.py --serial COM7` |

`r g b` / `hex` is the measured floor color. `led` / `led_hex` is what the LEDs show (brighter and more saturated). `/color` allows requests from other web pages, so the phone page of the game can fetch it too.

## Tuning

All settings are at the top of the `.ino` file:

| Setting | What it does |
|---|---|
| `LED_COUNT`, `LED_PIN` | number of LEDs and the data pin |
| `LED_BRIGHTNESS` | overall LED brightness (0–255) |
| `SATURATION_BOOST` | how much more vivid the LEDs are than the floor |
| `SMOOTHING` | lower = slower, calmer color changes |
| `DARK_LEVEL`, `FULL_LEVEL` | floor brightness at which the LEDs are off / fully on |
| `SAMPLE_FRACTION` | which part of the image is averaged (0.5 = the middle half) |

Not tested on the real hardware yet. The code was syntax-checked against the official esp32-camera headers, but not compiled with the full ESP32 toolchain: do a first Verify in the Arduino IDE.
