# ESP32 camera colour reader

`esp32-camera-color.ino` reads the colour in front of an ESP32 camera module and prints it on the Serial Monitor:

```
COLOR 200 40 30 #C8281E red
```

It works on a **Seeed XIAO ESP32-S3 Sense** (default) or an **AI-Thinker ESP32-CAM**. Choose your board in the `BOARD SELECTION` block at the top of the sketch.

## Upload

1. Arduino IDE → Boards Manager → install **esp32 by Espressif Systems**. No extra libraries are needed.
2. Open `esp32-camera-color/esp32-camera-color.ino`.
3. Tools → Board:
   - XIAO: **XIAO_ESP32S3**, and set PSRAM to **OPI PSRAM**
   - ESP32-CAM: **AI Thinker ESP32-CAM** (needs a USB-serial adapter or ESP32-CAM-MB board; hold IO0 to GND while uploading)
4. Upload and open the Serial Monitor at **115200** baud.

## Use

- Point the camera at a surface 3–6 cm away. It averages the middle half of the image.
- Do a **white calibration** once: hold a white sheet of paper in front of the camera and type `w`. The calibration is saved in flash.
- `r` resets the calibration, `i` prints info.
- The status LED stays on while it runs and blinks fast if the camera did not start.

Settings (smoothing, sampled area, print rate, ESP32-CAM flash LED) are at the top of the sketch.

Not compiled or tested on hardware yet. Start with Verify in the Arduino IDE.
