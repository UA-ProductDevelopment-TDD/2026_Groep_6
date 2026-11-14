"""Set the Bittle's chameleon LEDs live to the most common colour in the middle of the webcam image.

Same idea as photo_to_leds.py (and it uses its colour code), but with live webcam frames instead of photos.
A window shows the webcam image, the square in the middle that is measured, and the LED colour.

Install once:   pip install pillow pyserial opencv-python
Use:            python webcam_to_leds.py --studio                 (Bittle Studio only, no robot needed)
                python webcam_to_leds.py --port COM3              (real Bittle)
                python webcam_to_leds.py --port COM3 --studio     (both)
                python webcam_to_leds.py --studio --camera 1      (another webcam, if you have more than one)
Stop with q or Esc in the webcam window, or Ctrl+C in the terminal.
Close the Arduino Serial Monitor first, and don't connect Bittle Studio itself to the same COM port.
"""
import argparse
import sys
import time

import cv2
import serial
from PIL import Image

import photo_to_leds as leds

SEND_EVERY = 0.3     # seconds between colour measurements
MIN_CHANGE = 25      # only send when the LED colour changed this much (sum of R, G, B differences), to keep it calm


def open_camera(index):
    # On Windows, DirectShow opens most USB webcams faster and more reliably than the default backend.
    camera = cv2.VideoCapture(index, cv2.CAP_DSHOW) if sys.platform == 'win32' else cv2.VideoCapture(index)
    if not camera.isOpened():
        raise SystemExit('Could not open webcam %d. Is it plugged in, and not in use by another program (Teams, Zoom, '
                         'the Camera app)? With more than one webcam, try --camera 1.' % index)
    return camera


def draw(frame, led):
    """Mark the measured middle part and show the LED colour in the corner."""
    h, w = frame.shape[:2]
    dx, dy = round(w * (1 - leds.CENTER_FRACTION) / 2), round(h * (1 - leds.CENTER_FRACTION) / 2)
    cv2.rectangle(frame, (dx, dy), (w - dx, h - dy), (255, 255, 255), 2)
    if led:
        cv2.rectangle(frame, (10, 10), (90, 60), led[::-1], -1)  # OpenCV uses BGR
        cv2.rectangle(frame, (10, 10), (90, 60), (255, 255, 255), 1)
        cv2.putText(frame, 'LEDs %d %d %d' % led, (100, 42), cv2.FONT_HERSHEY_SIMPLEX, .6, (255, 255, 255), 2)
    cv2.putText(frame, 'q / Esc: stop', (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--port', help='COM port of the Bittle, e.g. COM3')
    parser.add_argument('--studio', action='store_true', help='also show the colour on the virtual LEDs in Bittle Studio')
    parser.add_argument('--camera', type=int, default=0, help='webcam number (default 0; try 1 if you have more)')
    parser.add_argument('--pin', type=int, default=9, help='GPIO of the LED strip (default 9; 0 = keep the pin set in the .ino)')
    parser.add_argument('--no-window', action='store_true', help="don't show the webcam window")
    args = parser.parse_args()
    if not (args.port or args.studio):
        parser.error('give --port (real Bittle) and/or --studio (Bittle Studio)')

    camera = open_camera(args.camera)
    port = serial.Serial(args.port, 115200, timeout=0.5) if args.port else None
    try:
        if port:
            if not leds.wait_until_ready(port):
                return
            if args.pin:
                print('LED pin:', leds.command(port, 'v pin %d' % args.pin) or '(no answer)')
                leds.command(port, 'v off')
        print('Running. Point the webcam at something colourful.')
        sent, last_check = None, 0.
        while True:
            ok, frame = camera.read()
            if not ok:
                print('The webcam stopped giving images.')
                break
            if time.time() - last_check >= SEND_EVERY:
                last_check = time.time()
                rgb = leds.dominant_colour_of(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
                led = leds.led_colour(rgb)
                if sent is None or sum(abs(a - b) for a, b in zip(led, sent)) >= MIN_CHANGE:
                    print('webcam -> most common colour in the middle: %d %d %d, LEDs: %d %d %d' % (rgb + led))
                    leds.send(port, led, args.studio)
                    sent = led
            if not args.no_window:
                draw(frame, sent)
                cv2.imshow('Chameleon webcam', frame)
                if cv2.waitKey(1) & 0xFF in (ord('q'), 27):
                    break
                if cv2.getWindowProperty('Chameleon webcam', cv2.WND_PROP_VISIBLE) < 1:  # window closed with the X
                    break
            else:
                time.sleep(.03)
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
