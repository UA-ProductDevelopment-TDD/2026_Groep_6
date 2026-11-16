// Chameleon tongue: one SG90 servo (180 degrees) that moves the tongue between two positions, steered over serial or Bluetooth.
// Turned on with "#define CHAMELEON_TONGUE" in OpenCatEsp32.ino. Without that define, none of this is compiled.
//
// Wiring (our robot): socket 14 = joint 1 = GPIO 14. Orange = signal, brown = GND on the header,
// red = a +5V pin (NOT the middle pin of the header: that one carries the battery voltage, too much for an SG90).
// The Grove ports can't drive a servo: G3/G4 are input-only, G2 is the I2C bus of the IMU.
//
// The tongue servo is driven like a normal hobby servo: 50 Hz, 500-2400 us for 0-180 degrees,
// exactly like our ESP32 test sketch. (OpenCat drives its own Petoi servos at 240 Hz with another scale;
// espServo.h gives the tongue joint this SG90 setting instead.)
//
// Serial Monitor (115200 baud, line ending "Newline"):
//   y 10           tongue to 10 degrees
//   y 100          tongue to 100 degrees
//   y              switch between the "in" and "out" position (10 and 100 by default)
//   y in / y out   go to the "in" / "out" position
//   y flick 3      out and back in, 3 times
//   y set in 10    change the "in" angle (until the next restart), likewise "y set out 100", "y set hold 300"
//   y ?            print joint, angles and hold time
//
// Note: posture skills such as "ksit" also set this joint, which puts the tongue in the middle (90 degrees).

#ifndef TONGUE_JOINT
#define TONGUE_JOINT 2  // OpenCat joint index of the tongue servo
#endif
#ifndef TONGUE_IN_ANGLE
#define TONGUE_IN_ANGLE 10  // SG90 degrees, 0-180
#endif
#ifndef TONGUE_OUT_ANGLE
#define TONGUE_OUT_ANGLE 100
#endif
#ifndef TONGUE_HOLD_MS
#define TONGUE_HOLD_MS 300  // how long the tongue stays out during a flick
#endif

#define T_TONGUE 'y'

int tongueInAngle = TONGUE_IN_ANGLE;
int tongueOutAngle = TONGUE_OUT_ANGLE;
int tongueHoldMs = TONGUE_HOLD_MS;

int tongueAngle = TONGUE_IN_ANGLE;

void tongueMove(int angle) {
  tongueAngle = constrain(angle, 0, 180);
  byte s = (PWM_NUM == 12 && TONGUE_JOINT > 3) ? TONGUE_JOINT - 4 : TONGUE_JOINT;  // joint index -> PWM channel
  if (!servo[s].attached())
    servo[s].attach(PWM_pin[s], modelObj[s]);
  servo[s].write(tongueAngle);  // the SG90 model maps 0-180 degrees to 500-2400 us at 50 Hz
}

void tongueFlick(int times = 1) {
  for (int i = 0; i < times; i++) {
    tongueMove(tongueOutAngle);
    delay(tongueHoldMs);
    tongueMove(tongueInAngle);
    if (i + 1 < times)
      delay(tongueHoldMs);
  }
}

void tonguePrintState() {
  char line[96];
  snprintf(line, sizeof(line), "Tongue joint %d, in %d, out %d, hold %d ms, now %d", TONGUE_JOINT, tongueInAngle,
           tongueOutAngle, tongueHoldMs, tongueAngle);
  printToAllPorts(line);
}

void tongueCommand(const char *cmd) {
  while (*cmd == ' ')
    cmd++;
  int a;
  char what[8];
  if (*cmd == '\0') {
    tongueMove(tongueAngle == tongueOutAngle ? tongueInAngle : tongueOutAngle);
  } else if (*cmd == '?') {
    // only print
  } else if (!strncmp(cmd, "flick", 5)) {
    if (sscanf(cmd + 5, "%d", &a) != 1)
      a = 1;
    tongueFlick(constrain(a, 1, 20));
  } else if (!strncmp(cmd, "out", 3)) {
    tongueMove(tongueOutAngle);
  } else if (!strncmp(cmd, "in", 2)) {
    tongueMove(tongueInAngle);
  } else if (!strncmp(cmd, "set", 3)) {
    if (sscanf(cmd + 3, "%7s %d", what, &a) != 2) {
      printToAllPorts("Use: y set out 100, y set in 10 or y set hold 300");
      return;
    }
    if (!strcmp(what, "out"))
      tongueOutAngle = constrain(a, 0, 180);
    else if (!strcmp(what, "in"))
      tongueInAngle = constrain(a, 0, 180);
    else if (!strcmp(what, "hold"))
      tongueHoldMs = constrain(a, 0, 5000);
    else {
      printToAllPorts("Use: y set out 100, y set in 10 or y set hold 300");
      return;
    }
  } else if (sscanf(cmd, "%d", &a) == 1) {
    tongueMove(a);
  } else {
    printToAllPorts("Use: y 10, y 100, y, y in, y out, y flick 3, y set out 100, y ?");
    return;
  }
  tonguePrintState();
}
