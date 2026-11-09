"""Set the Bittle's chameleon LEDs to the most common colour in the middle of a photo.

The script looks at a folder of photos, computes the most common colour in the middle of the
newest photo and sends "v r g b" over USB to the Bittle (the same command you type in
the Serial Monitor). With --watch it keeps watching the folder: drop in a new
photo and the LEDs change.

Install once:   pip install pillow pyserial
Use:            python photo_to_leds.py --port COM5
                python photo_to_leds.py --port COM5 --watch
                python photo_to_leds.py --port COM5 --photo fotos/gras.jpg
                python photo_to_leds.py --list-ports
Close the Arduino Serial Monitor first: only one program can use the COM port.
"""
import argparse
import colorsys
import time
from pathlib import Path

import serial
import serial.tools.list_ports
from PIL import Image

HERE = Path(__file__).parent
CENTER_FRACTION = 0.5  # use the middle part of the photo (0.5 = middle half of width and height)
SATURATION_BOOST = 2.0  # LEDs look washed out (whitish) with photo colours; make them this much more vivid
GAMMA = 2.2             # LEDs are linear, eyes are not: without this, mixed colours look too white
PHOTO_TYPES = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}


def dominant_colour(path, groups=8):
    """Most common colour in the middle of the photo: group similar colours into `groups` clusters and return the biggest cluster's colour."""
    with Image.open(path) as img:
        img = img.convert('RGB')
        w, h = img.size
        dx, dy = round(w * (1 - CENTER_FRACTION) / 2), round(h * (1 - CENTER_FRACTION) / 2)
        img = img.crop((dx, dy, w - dx, h - dy))  # only the middle of the photo
        img.thumbnail((200, 200))
        small = img.quantize(colors=groups, method=Image.Quantize.MEDIANCUT)
    palette = small.getpalette()
    count, index = max(small.getcolors())
    return tuple(palette[3 * index:3 * index + 3])


def led_colour(rgb):
    """Photo colour -> LED colour: more saturated, full brightness, gamma corrected."""
    h, sat, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    r, g, b = colorsys.hsv_to_rgb(h, min(1.0, sat * SATURATION_BOOST), 1.0)
    return tuple(round(255 * c ** GAMMA) for c in (r, g, b))


def newest_photo(folder):
    photos = [p for p in folder.iterdir() if p.suffix.lower() in PHOTO_TYPES]
    return max(photos, key=lambda p: p.stat().st_mtime) if photos else None


def command(port, line, wait=2.0):
    """Send one line and return the Bittle's 'LED ...' answer, or '' if none came within `wait` seconds."""
    port.reset_input_buffer()
    port.write((line + '\n').encode())
    end = time.time() + wait
    while time.time() < end:
        reply = port.readline().decode(errors='replace').strip()
        if reply.startswith('LED') or reply.startswith('Use:') or reply.startswith('This pin'):
            return reply
    return ''


def wait_until_ready(port, timeout=40):
    """Opening the port restarts the ESP32; ask 'v ?' every few seconds until OpenCat answers."""
    print('Waiting for the Bittle to start (can take up to ~20 s)...')
    end = time.time() + timeout
    while time.time() < end:
        if command(port, 'v ?', wait=3):
            print('Bittle is ready.')
            return True
    print('The Bittle did not answer to "v ?". Is the right .ino (with CHAMELEON_LED) uploaded, and the Serial Monitor closed?')
    return False


def send(port, rgb):
    line = 'v %d %d %d' % rgb
    print('sent:', line, '| Bittle:', command(port, line) or '(no answer)')


def show(port, photo):
    rgb = dominant_colour(photo)
    led = led_colour(rgb)
    print('%s -> most common colour in the middle: %d %d %d (#%02X%02X%02X), LEDs: %d %d %d'
          % ((photo.name,) + rgb + rgb + led))
    send(port, led)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--port', help='COM port of the Bittle, e.g. COM5 (see --list-ports)')
    parser.add_argument('--folder', default=str(HERE / 'fotos'), help='folder with photos (default: fotos next to this script)')
    parser.add_argument('--photo', help='use this one photo instead of the newest in the folder')
    parser.add_argument('--watch', action='store_true', help='keep watching the folder for new photos')
    parser.add_argument('--pin', type=int, default=9, help='GPIO of the LED strip (default 9; 0 = keep the pin set in the .ino)')
    parser.add_argument('--list-ports', action='store_true', help='show the available COM ports and stop')
    args = parser.parse_args()

    if args.list_ports or not args.port:
        for p in serial.tools.list_ports.comports():
            print(p.device, '-', p.description)
        if not args.port:
            print('\nStart again with --port and the Bittle\'s port, e.g. --port COM5')
        return

    folder = Path(args.folder)
    folder.mkdir(exist_ok=True)
    with serial.Serial(args.port, 115200, timeout=0.5) as port:
        if not wait_until_ready(port):
            return
        if args.pin:
            print('LED pin:', command(port, 'v pin %d' % args.pin) or '(no answer)')
            command(port, 'v off')  # 'v pin' lights the strip white as a test; switch that off again

        if args.photo:
            show(port, Path(args.photo))
            return
        last = None
        while True:
            photo = newest_photo(folder)
            if photo is None and last is None:
                print('No photos in', folder.resolve(), '- put a .jpg or .png there.')
                last = 'empty'
            if photo is not None:
                key = (photo, photo.stat().st_mtime)
                if key != last:
                    show(port, photo)
                    last = key
            if not args.watch:
                return
            time.sleep(1)


if __name__ == '__main__':
    main()
