"""Set the Bittle's chameleon LEDs live to the colour of the object in the middle of the webcam image.

Same idea as photo_to_leds.py, but with live webcam frames, and with extra work to make the LEDs look like the
real object, also for dark and dull colours:
Everything is automatic; you only point the webcam at the object.
  1. Camera: auto exposure and auto white balance are LOCKED after a short warm-up. Otherwise the webcam makes a dark
     object brighter and greyer, and shifts its colour, the moment you hold it in front of the lens. When the room
     gets clearly lighter or darker (lamp on/off), the script lets the camera adjust once more and locks it again.
  2. White balance and "how bright is white": measured all the time on the room AROUND the square (the object is in
     the square), so a yellow lamp or a blue-ish webcam is corrected, and a dark object is seen as dark, not grey.
     If the object fills the whole image, the last good measurement is kept.
  3. Colour: the object's colour is measured on the pixels with the most colour, so a dark object still gives its
     hue. Grey stays grey (white LEDs), dark objects give dimmer LEDs, and - / + make the LEDs softer / more vivid.
  4. LEDs: gamma and LED colour correction, because the strip's green is much stronger than its red and blue.

Install once:   pip install pillow pyserial opencv-python
Use:            python webcam_to_leds.py --studio                 (Bittle Studio only, no robot needed)
                python webcam_to_leds.py --port COM5              (real Bittle)
                python webcam_to_leds.py --port COM5 --studio     (both)
                python webcam_to_leds.py --port COM5 --camera 1   (another webcam, if you have more than one)
                python webcam_to_leds.py --list-cameras           (which camera numbers give an image?)
Keys in the webcam window (all optional, you don't need them):
    w       white balance on a white sheet of paper held in the square (even more exact); r = back to automatic
    [ ]     camera darker / brighter (exposure); a = automatic exposure again
    s       open the webcam driver's own settings window (Windows), for brightness, saturation, focus, ...
    - +     LED colours softer / more vivid (saturation), live
    b       LED brightness follows the object (dark object = dim LEDs) on/off
    q, Esc  stop (or Ctrl+C in the terminal)
Close the Arduino Serial Monitor first, and don't connect Bittle Studio itself to the same COM port.
"""
import argparse
import colorsys
import sys
import time

import cv2
import numpy as np
import serial

import photo_to_leds as leds

SEND_EVERY = 0.3     # seconds between colour measurements
MIN_CHANGE = 25      # only send when the LED colour changed this much (sum of R, G, B differences), to keep it calm
DARK = 20            # camera image darker than this (0-255) counts as black: lens covered or wrong camera
RELOCK_CHANGE = 0.35  # room brightness changed this much (35%) for RELOCK_AFTER seconds: let the camera adjust again
RELOCK_AFTER = 2.0
WB_SPEED = 0.25      # how fast the automatic white balance follows the room (0-1 per measurement)
MAX_GAIN = 1.6       # automatic white balance never changes a colour channel more than this (or 1/this)

# Colour -> LED settings (all can be changed with command line options, see --help)
SATURATION_BOOST = 1.0           # >1 makes dull colours more vivid, <1 makes all colours softer (keys - and +)
GREY = 0.12                      # objects with less saturation than this (0-1) are grey/white: white LEDs
MIN_CHROMA = 6                   # and colour differences below this (0-255) are camera noise, not colour
MIN_LED_BRIGHTNESS = 0.25        # dimmest LED brightness (0-1) for a very dark object, when brightness follows
BLACK = 0.06                     # object darker than this (0-1, after white balance) and grey: LEDs off
LED_BALANCE = (1.0, 0.69, 0.94)  # WS2812 LEDs: green is strongest, so turn it down for real white (FastLED 0xFFB0F0)


# ---------------------------------------------------------------- camera

def backends():
    """Windows has two video drivers; some webcams only give black frames with one of them.
    DirectShow first: it is the one that lets us lock exposure and white balance."""
    if sys.platform == 'win32':
        return [('DirectShow', cv2.CAP_DSHOW), ('Media Foundation', cv2.CAP_MSMF)]
    return [('default', cv2.CAP_ANY)]


def brightness(camera, tries=15):
    """Average brightness (0-255) of the camera image after a short warm-up, or None if it gives no images."""
    level = None
    for _ in range(tries):  # many webcams send a few black frames while they start
        ok, frame = camera.read()
        if ok and frame is not None:
            level = float(frame.mean())
            if level > DARK:
                break
        time.sleep(.05)
    return level


def open_camera(index):
    """Open webcam `index` with the first Windows video driver that gives a real (not black) image."""
    found = None
    for name, backend in backends():
        camera = cv2.VideoCapture(index, backend)
        if not camera.isOpened():
            continue
        level = brightness(camera)
        if level is not None and level > DARK:
            if found is not None:
                found.release()
            print('Webcam %d opened (%s).' % (index, name))
            return camera
        if found is None and level is not None:
            found = camera  # gives images, but dark: keep it in case the room is simply dark
        else:
            camera.release()
    if found is not None:
        print('Webcam %d only gives a (nearly) black image. Lens covered or privacy shutter closed? '
              'Or the wrong camera? Try: python webcam_to_leds.py --list-cameras' % index)
        return found
    raise SystemExit('Could not open webcam %d. Is it plugged in, and not in use by another program (Teams, Zoom, '
                     'the Camera app)? Try: python webcam_to_leds.py --list-cameras' % index)


def list_cameras():
    print('Checking camera numbers 0-5 (takes a few seconds)...')
    for index in range(6):
        results = []
        for name, backend in backends():
            camera = cv2.VideoCapture(index, backend)
            if camera.isOpened():
                level = brightness(camera)
                results.append('%s: %s' % (name, 'no image' if level is None else
                                           'black image' if level <= DARK else 'image OK (brightness %d)' % level))
            camera.release()
        if results:
            print('  --camera %d   ' % index + ' | '.join(results))
    print('Use a number that says "image OK", e.g. python webcam_to_leds.py --port COM5 --camera 1')


def settle(camera, seconds):
    """Keep reading frames so auto exposure / white balance can adjust (frames pile up otherwise)."""
    end = time.time() + seconds
    while time.time() < end:
        camera.read()


def set_auto(camera, on):
    """Auto exposure and auto white balance on or off. Drivers disagree on the values: Windows uses 1/0 (some
    versions 0.75/0.25), Linux (V4L2) uses 3 = auto and 1 = manual. The last value set is the one that counts."""
    if sys.platform == 'win32':
        values = (0.75, 1) if on else (0.25, 0)
    else:
        values = (0.75, 3) if on else (0.25, 1)
    for value in values:
        camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, value)
    camera.set(cv2.CAP_PROP_AUTO_WB, 1 if on else 0)


def lock_camera(camera, settle_time=2.0):
    """Let the camera choose exposure and white balance once (on the normal scene), then freeze them."""
    set_auto(camera, True)
    settle(camera, settle_time)
    exposure, temperature = camera.get(cv2.CAP_PROP_EXPOSURE), camera.get(cv2.CAP_PROP_WB_TEMPERATURE)
    set_auto(camera, False)
    if exposure:  # 0 means: this driver does not tell us; then freezing keeps whatever it had
        camera.set(cv2.CAP_PROP_EXPOSURE, exposure)
    if temperature > 0:
        camera.set(cv2.CAP_PROP_WB_TEMPERATURE, temperature)
    print('Camera locked: exposure %s, white balance %s.' % (
        '%g' % exposure if exposure else '(not reported)', '%d K' % temperature if temperature > 0 else '(not reported)'))


def change_exposure(camera, step):
    """One step darker (-1) or brighter (+1). On Windows the exposure is a power of 2 (-6 = 1/64 s)."""
    now = camera.get(cv2.CAP_PROP_EXPOSURE)
    new = now + step if now <= 0 else now * (1.4 if step > 0 else 1 / 1.4)
    set_auto(camera, False)
    camera.set(cv2.CAP_PROP_EXPOSURE, new)
    got = camera.get(cv2.CAP_PROP_EXPOSURE)
    print('Exposure: %g -> %g%s' % (now, got, '' if got != now else
                                    ' (this webcam ignores it here; press s for the driver settings)'))


def apply_camera_options(camera, args):
    """--exposure, --camera-brightness, --camera-saturation, ... and report what the webcam accepted."""
    if args.auto_camera:
        set_auto(camera, True)
        print('Camera: auto exposure and auto white balance stay on (--auto-camera).')
    elif args.exposure is not None:
        set_auto(camera, False)
        camera.set(cv2.CAP_PROP_EXPOSURE, args.exposure)
        if args.wb_temperature:
            camera.set(cv2.CAP_PROP_WB_TEMPERATURE, args.wb_temperature)
        print('Camera: manual exposure %g (asked %g).' % (camera.get(cv2.CAP_PROP_EXPOSURE), args.exposure))
    else:
        print('Camera: finding exposure and white balance for 2 s, then locking them...')
        lock_camera(camera)
        if args.wb_temperature:
            camera.set(cv2.CAP_PROP_WB_TEMPERATURE, args.wb_temperature)
    for option, prop, name in ((args.camera_brightness, cv2.CAP_PROP_BRIGHTNESS, 'brightness'),
                               (args.camera_contrast, cv2.CAP_PROP_CONTRAST, 'contrast'),
                               (args.camera_saturation, cv2.CAP_PROP_SATURATION, 'saturation'),
                               (args.camera_gain, cv2.CAP_PROP_GAIN, 'gain')):
        if option is not None:
            before = camera.get(prop)
            camera.set(prop, option)
            print('Camera %s: %g -> %g' % (name, before, camera.get(prop)))


# ---------------------------------------------------------------- colour

def middle(frame):
    """The measured square in the middle of the frame (BGR), made small so it is fast."""
    h, w = frame.shape[:2]
    dx, dy = round(w * (1 - leds.CENTER_FRACTION) / 2), round(h * (1 - leds.CENTER_FRACTION) / 2)
    part = frame[dy:h - dy, dx:w - dx]
    scale = 80 / max(part.shape[:2])
    return cv2.resize(part, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else part


def surroundings(frame):
    """RGB pixels of the room around the measured square (the outer ring of the image), made small."""
    small = cv2.resize(frame, (64, 48), interpolation=cv2.INTER_AREA)[:, :, ::-1].astype(np.float32)
    h, w = small.shape[:2]
    dx, dy = round(w * (1 - leds.CENTER_FRACTION) / 2), round(h * (1 - leds.CENTER_FRACTION) / 2)
    mask = np.ones((h, w), bool)
    mask[dy:h - dy, dx:w - dx] = False
    return small[mask]


def measure_white(rgb):
    """Automatic white balance from pixels of the room: (gains R, G, B; brightness of white 0-255), or None.

    Gains: "shades of grey" (most rooms average out to grey, with the bright parts counting more), which works
    better than a plain average. White: the bright end of the room, ignoring clipped (overexposed) pixels.
    """
    if len(rgb) < 20 or rgb.mean() < 15:
        return None  # too dark to say anything
    ok = rgb[rgb.max(1) < 250]
    if len(ok) < 20:
        ok = rgb
    norm = np.mean(ok ** 6, axis=0) ** (1 / 6)
    gains = np.clip(norm.max() / np.maximum(norm, 1), 1 / MAX_GAIN, MAX_GAIN)
    white = float(np.percentile((ok * gains).max(1), 97))
    return gains, max(white, 60.0)


class WhiteBalance:
    """The white balance: automatic from the room around the square, or fixed from a white sheet of paper (key w)."""

    def __init__(self, automatic=True):
        self.automatic = automatic
        self.gains, self.white = np.ones(3), 255.0
        self.fixed = self.measured = False

    def update(self, frame, object_rgb=None):
        """Follow the room slowly. With object_rgb (already balanced) it first checks the object doesn't fill the image."""
        if not self.automatic or self.fixed:
            return
        room = surroundings(frame)
        if object_rgb is not None:
            # object fills (almost) the whole image: the "room" is the object, don't white-balance its colour away
            raw = np.float32(object_rgb) / self.gains
            near = np.abs(room - raw).sum(1) < 60
            if near.mean() > 0.6 and chroma(object_rgb) > 30:
                return
        found = measure_white(room)
        if found:
            k = WB_SPEED if self.measured else 1.0
            self.gains = (1 - k) * self.gains + k * found[0]
            self.white = (1 - k) * self.white + k * found[1]
            self.measured = True

    def apply(self, rgb):
        return np.clip(rgb * np.float32(self.gains), 0, 255)

    def calibrate(self, frame):
        """White sheet of paper in the square: exact gains and white level for this run."""
        rgb = middle(frame)[:, :, ::-1].reshape(-1, 3).astype(np.float32)
        bright = rgb[rgb.sum(1) >= np.percentile(rgb.sum(1), 25)]  # skip shadows / fingers
        mean = bright.mean(0)
        if mean.max() < 40:
            print('Too dark for a white balance: hold a white sheet of paper in the square, in the light.')
            return
        if mean.min() > 250:
            print('The white is overexposed (clipped): press [ a few times, then w again.')
        self.gains, self.white, self.fixed = mean.max() / np.maximum(mean, 1), float(mean.max()), True
        print('White balance from the paper: R x%.2f, G x%.2f, B x%.2f (white = %d/255). r = automatic again.'
              % (tuple(self.gains) + (self.white,)))

    def reset(self):
        self.fixed = False
        print('White balance: automatic again.')

    def describe(self):
        if not self.automatic:
            return 'off'
        return '%s (R%.2f G%.2f B%.2f, white %d)' % (('paper' if self.fixed else 'auto',) + tuple(self.gains)
                                                     + (self.white,))


class ExposureWatch:
    """Notices when the room gets clearly lighter or darker for a while (lamp, curtains), so the camera can re-adjust."""

    def __init__(self, camera):
        self.reference, self.since = scene_brightness(camera), None

    def changed(self, frame):
        level = float(surroundings(frame).mean())
        if self.reference is None:
            self.reference = level
        if abs(level - self.reference) <= RELOCK_CHANGE * max(self.reference, 20):
            self.since = None
            return False
        self.since = self.since or time.time()
        return time.time() - self.since >= RELOCK_AFTER

    def reset(self, level):
        self.reference, self.since = level, None


def scene_brightness(camera):
    ok, frame = camera.read()
    return float(surroundings(frame).mean()) if ok and frame is not None else None


def object_colour(frame, balance, groups=4):
    """Colour (R, G, B 0-255, white balanced) of the object in the middle square.

    The pixels are grouped into `groups` colours (k-means); the biggest group is the object. Its colour is the
    median of its pixels, so noise and highlights don't wash it out. If the biggest group is grey but another big
    group (at least half as big) has real colour, that one wins: a dark or shiny object often has grey reflections.
    """
    rgb = middle(frame)[:, :, ::-1].reshape(-1, 3).astype(np.float32)
    rgb = balance.apply(rgb)
    groups = min(groups, len(rgb))
    _, labels, _ = cv2.kmeans(rgb, groups, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0),
                              2, cv2.KMEANS_PP_CENTERS)
    labels = labels.ravel()
    sizes = np.bincount(labels, minlength=groups)
    order = np.argsort(sizes)[::-1]
    colours = [np.median(rgb[labels == i], axis=0) for i in order]
    best = colours[0]
    for colour, size in zip(colours[1:], sizes[order][1:]):
        if size >= sizes[order[0]] / 2 and chroma(colour) > 2 * chroma(best) and chroma(colour) >= 2 * MIN_CHROMA:
            best = colour
            break
    return tuple(int(round(c)) for c in best)


def chroma(rgb):
    return float(max(rgb) - min(rgb))


def led_colour(rgb, white=255.0, follow_brightness=True, boost=SATURATION_BOOST, balance=LED_BALANCE, gamma=leds.GAMMA):
    """Object colour -> LED colour.

    - hue: kept as it is, also for dark objects (HSV saturation does not depend on brightness)
    - saturation: dull colours are boosted more than vivid ones, grey stays grey
    - brightness: relative to white (measured on the room); dark object = dimmer LEDs, never fully off unless black
    - gamma + LED balance: LEDs are linear and their green is too strong
    """
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    level = min(1.0, v * 255 / max(white, 1))
    if s < GREY or chroma(rgb) < MIN_CHROMA:
        if level < BLACK:
            return 0, 0, 0
        s = 0.0
    else:
        s = ((s - GREY) / (1 - GREY)) ** (1 / boost)  # smooth from grey (0) up, dull colours boosted most
    if follow_brightness:
        level = MIN_LED_BRIGHTNESS + (1 - MIN_LED_BRIGHTNESS) * level ** 0.5  # eyes see brightness as a square root
    else:
        level = 1.0
    r, g, b = colorsys.hsv_to_rgb(h, s, level)
    return tuple(int(round(255 * k * c ** gamma)) for k, c in zip(balance, (r, g, b)))


# ---------------------------------------------------------------- window

def draw(frame, led, rgb, info):
    """Mark the measured middle part, show the measured colour and the LED colour."""
    h, w = frame.shape[:2]
    dx, dy = round(w * (1 - leds.CENTER_FRACTION) / 2), round(h * (1 - leds.CENTER_FRACTION) / 2)
    cv2.rectangle(frame, (dx, dy), (w - dx, h - dy), (255, 255, 255), 2)
    if rgb:
        cv2.rectangle(frame, (10, 10), (60, 60), rgb[::-1], -1)  # OpenCV uses BGR
        cv2.rectangle(frame, (10, 10), (60, 60), (255, 255, 255), 1)
        cv2.putText(frame, 'object %d %d %d' % rgb, (70, 30), cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)
    if led:
        cv2.rectangle(frame, (10, 66), (60, 116), led[::-1], -1)
        cv2.rectangle(frame, (10, 66), (60, 116), (255, 255, 255), 1)
        cv2.putText(frame, 'LEDs %d %d %d' % led, (70, 96), cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)
    cv2.putText(frame, info, (10, h - 32), cv2.FONT_HERSHEY_SIMPLEX, .45, (255, 255, 255), 1)
    cv2.putText(frame, '- + saturation  w white  [ ] exposure  a auto  s settings  b brightness  q stop',
                (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, .45, (255, 255, 255), 1)


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--port', help='COM port of the Bittle, e.g. COM5')
    parser.add_argument('--studio', action='store_true', help='also show the colour on the virtual LEDs in Bittle Studio')
    parser.add_argument('--camera', type=int, default=0, help='webcam number (default 0; try 1 if you have more)')
    parser.add_argument('--pin', type=int, default=9, help='GPIO of the LED strip (default 9; 0 = keep the pin set in the .ino)')
    parser.add_argument('--list-cameras', action='store_true', help='show which camera numbers give an image, and stop')
    parser.add_argument('--no-window', action='store_true', help="don't show the webcam window")
    camera_group = parser.add_argument_group('camera settings')
    camera_group.add_argument('--auto-camera', action='store_true',
                              help='keep auto exposure and auto white balance on (the old behaviour)')
    camera_group.add_argument('--exposure', type=float,
                              help='fixed exposure instead of locking the automatic one (Windows: e.g. -6; lower = darker)')
    camera_group.add_argument('--wb-temperature', type=int, help='fixed camera white balance in Kelvin, e.g. 4500')
    camera_group.add_argument('--camera-brightness', type=float, help="webcam's own brightness setting")
    camera_group.add_argument('--camera-contrast', type=float, help="webcam's own contrast setting")
    camera_group.add_argument('--camera-saturation', type=float, help="webcam's own saturation setting")
    camera_group.add_argument('--camera-gain', type=float, help="webcam's own gain setting")
    camera_group.add_argument('--settings', action='store_true', help="open the webcam driver's settings window at the start (Windows)")
    colour_group = parser.add_argument_group('colour settings')
    colour_group.add_argument('--boost', type=float, default=SATURATION_BOOST,
                              help='saturation: >1 more vivid, <1 softer (default %g; keys - and + change it live)' % SATURATION_BOOST)
    colour_group.add_argument('--full-brightness', action='store_true',
                              help='LEDs always at full brightness, also for dark objects (key b toggles it)')
    colour_group.add_argument('--led-balance', type=float, nargs=3, metavar=('R', 'G', 'B'), default=LED_BALANCE,
                              help='LED colour correction, 0-1 per colour (default %g %g %g; 1 1 1 = none)' % LED_BALANCE)
    colour_group.add_argument('--no-white-balance', action='store_true', help='no automatic white balance')
    args = parser.parse_args()
    if args.list_cameras:
        list_cameras()
        return
    if not (args.port or args.studio):
        parser.error('give --port (real Bittle) and/or --studio (Bittle Studio)')

    camera = open_camera(args.camera)
    apply_camera_options(camera, args)
    if args.settings:
        camera.set(cv2.CAP_PROP_SETTINGS, 1)
    balance = WhiteBalance(automatic=not args.no_white_balance)
    auto_relock = not (args.auto_camera or args.exposure is not None)
    watch = ExposureWatch(camera)
    ok, frame = camera.read()
    if ok:
        balance.update(frame)  # first white balance: from the whole room
    follow = not args.full_brightness
    boost = args.boost
    port = serial.Serial(args.port, 115200, timeout=0.5) if args.port else None
    try:
        if port:
            if not leds.wait_until_ready(port):
                return
            if args.pin:
                print('LED pin:', leds.command(port, 'v pin %d' % args.pin) or '(no answer)')
                leds.command(port, 'v off')
        print('Running. Point the webcam at something colourful.')
        sent, rgb, last_check = None, None, 0.
        while True:
            ok, frame = camera.read()
            if not ok:
                print('The webcam stopped giving images.')
                break
            if time.time() - last_check >= SEND_EVERY:
                last_check = time.time()
                if auto_relock and watch.changed(frame):
                    print('The light in the room changed: camera adjusts again...')
                    lock_camera(camera, 1.5)
                    watch.reset(scene_brightness(camera))
                    continue
                rgb = object_colour(frame, balance)
                balance.update(frame, rgb)  # for the next measurement
                led = led_colour(rgb, balance.white, follow, boost, args.led_balance)
                if sent is None or sum(abs(a - b) for a, b in zip(led, sent)) >= MIN_CHANGE:
                    print('webcam -> object colour in the middle: %d %d %d, LEDs: %d %d %d' % (rgb + led))
                    leds.send(port, led, args.studio)
                    sent = led
            if args.no_window:
                time.sleep(.03)
                continue
            info = 'white balance %s | saturation %.2f | LED brightness %s' % (
                balance.describe(), boost, 'follows object' if follow else 'full')
            shown = frame.copy()
            draw(shown, sent, rgb, info)
            cv2.imshow('Chameleon webcam', shown)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), 27):
                break
            if key == ord('w'):
                balance.calibrate(frame)
                sent = None
            elif key == ord('r'):
                balance.reset()
                sent = None
            elif key in (ord('['), ord(']')):
                change_exposure(camera, 1 if key == ord(']') else -1)
                auto_relock = False  # you chose the exposure yourself: don't undo it when the light changes
            elif key == ord('a'):
                lock_camera(camera)
                watch.reset(scene_brightness(camera))
                auto_relock = not args.auto_camera
            elif key == ord('s'):
                camera.set(cv2.CAP_PROP_SETTINGS, 1)
            elif key in (ord('-'), ord('_'), ord('+'), ord('=')):
                boost = min(4.0, max(0.25, boost * (1.25 if key in (ord('+'), ord('=')) else 0.8)))
                print('Saturation %.2f (start with --boost %.2f to keep this)' % (boost, boost))
                sent = None
            elif key == ord('b'):
                follow = not follow
                print('LED brightness', 'follows the object' if follow else 'always full')
                sent = None
            if cv2.getWindowProperty('Chameleon webcam', cv2.WND_PROP_VISIBLE) < 1:  # window closed with the X
                break
    except KeyboardInterrupt:
        pass
    finally:
        camera.release()
        if not args.no_window:
            cv2.destroyAllWindows()
        if port:
            port.close()


if __name__ == '__main__':
    main()
