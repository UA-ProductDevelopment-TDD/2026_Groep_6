"""Read the floor color from the Bittle's XIAO camera.

Over WiFi (no extra packages needed):
    python read_color.py --url http://bittle-cam.local
    python read_color.py --url http://192.168.4.1        (camera's own "Bittle-Cam" network)

Over USB cable (needs: pip install pyserial):
    python read_color.py --serial COM7

Use it from your own code:
    from read_color import get_color
    color = get_color("http://bittle-cam.local")   # {'r': .., 'g': .., 'b': .., 'hex': '#..', 'led': [..], ...}
"""
import argparse
import json
import time
import urllib.request


def get_color(url, timeout=2.0):
    """Return the latest color measurement from the camera as a dict."""
    with urllib.request.urlopen(url.rstrip("/") + "/color", timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def parse_serial_line(line):
    """'COLOR 12 200 40 #0CC828' -> {'r': 12, 'g': 200, 'b': 40, 'hex': '#0CC828'} (or None)."""
    parts = line.strip().split()
    if len(parts) != 5 or parts[0] != "COLOR":
        return None
    r, g, b = (int(p) for p in parts[1:4])
    return {"r": r, "g": g, "b": b, "hex": parts[4]}


def swatch(c):
    """Colored block for terminals that support 24-bit color (Windows Terminal, VS Code)."""
    return f"\x1b[48;2;{c['r']};{c['g']};{c['b']}m      \x1b[0m"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="camera address, e.g. http://bittle-cam.local")
    src.add_argument("--serial", help="COM port of the XIAO, e.g. COM7")
    ap.add_argument("--rate", type=float, default=5, help="readings per second over WiFi (default 5)")
    args = ap.parse_args()

    if args.url:
        while True:
            try:
                c = get_color(args.url)
                print(f"{swatch(c)} floor {c['hex']}  rgb=({c['r']},{c['g']},{c['b']})  leds={c['led_hex']}")
            except OSError as e:
                print("No answer from camera:", e)
            time.sleep(1 / args.rate)
    else:
        import serial  # pip install pyserial

        with serial.Serial(args.serial, 115200, timeout=1) as port:
            while True:
                c = parse_serial_line(port.readline().decode(errors="ignore"))
                if c:
                    print(f"{swatch(c)} floor {c['hex']}  rgb=({c['r']},{c['g']},{c['b']})")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
