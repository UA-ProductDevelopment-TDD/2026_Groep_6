"""Two-player Bittle controller.

One person steers the two left legs, the other the two right legs, each from
their own phone. This laptop script sits in the middle: it serves the phone
page, merges both players' input and sends joint angles to the Bittle over
USB or Bluetooth.

Run:  python server.py --serial COM5      (USB cable)
      python server.py --ble               (Bluetooth, finds the Bittle itself)
      python server.py --studio            (the simulated Bittle in Bittle Studio)
      python server.py --dry-run           (no robot, just prints the commands)
"""

import argparse
import asyncio
import json
import socket
import threading
import urllib.request
from pathlib import Path

from aiohttp import web, WSMsgType

# --------------------------------------------------------------------------
# Tuning. Angles are in degrees, as the OpenCat firmware uses them.
# Shoulder: a smaller angle swings the foot forward, a larger one backward.
# Knee: a smaller (more negative) angle folds the leg and lifts the foot.
# The defaults come from Bittle's own walking gait (wkF in InstinctBittleESP.h).
# --------------------------------------------------------------------------
LEGS = {
    # name: shoulder joint, knee joint
    "FL": {"shoulder": 8, "knee": 12},
    "FR": {"shoulder": 9, "knee": 13},
    "BR": {"shoulder": 10, "knee": 14},
    "BL": {"shoulder": 11, "knee": 15},
}
# Who controls which legs. Players pick a role on their phone; roles come in pairs.
ROLES = {
    "left": ["FL", "BL"], "right": ["FR", "BR"],      # split left / right
    "front": ["FL", "FR"], "back": ["BL", "BR"],      # split front / back
    "diag1": ["FL", "BR"], "diag2": ["FR", "BL"],     # split diagonally (like a walking gait)
}
FRONT = {"center": 42, "range": 28, "knee_at_front": 0, "knee_slope": 0.45}
BACK = {"center": 48, "range": 26, "knee_at_front": 0, "knee_slope": 0.45}
LIFT_DEGREES = 35       # how far the knee folds when the foot is fully lifted
SEND_RATE_HZ = 15       # how often new angles go to the robot (max)
START_COMMANDS = ["gb"]  # gyro balancing off, so the robot doesn't fight the players

ble_service = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"  # Petoi BLE UART
ble_rx_char = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"  # we write commands here

STATIC = Path(__file__).parent / "static"


def clamp(value, low, high):
    return max(low, min(high, value))


def leg_angles(name, swing, lift):
    """swing: -1 (back) .. +1 (forward), lift: 0 (planted) .. 1 (up)."""
    cfg = FRONT if name[0] == "F" else BACK
    shoulder = cfg["center"] - clamp(swing, -1, 1) * cfg["range"]
    front_most = cfg["center"] - cfg["range"]
    knee = cfg["knee_at_front"] + cfg["knee_slope"] * (shoulder - front_most)
    knee -= clamp(lift, 0, 1) * LIFT_DEGREES
    return round(shoulder), round(knee)


class Game:
    def __init__(self):
        self.legs = {name: {"swing": 0.0, "lift": 0.0} for name in LEGS}
        self.players = {role: set() for role in ROLES}
        self.changed = asyncio.Event()

    def command(self):
        parts = ["i"]
        for name, leg in LEGS.items():
            shoulder, knee = leg_angles(name, **self.legs[name])
            parts += [str(leg["shoulder"]), str(shoulder), str(leg["knee"]), str(knee)]
        return " ".join(parts)

    def reset(self):
        for leg in self.legs.values():
            leg.update(swing=0.0, lift=0.0)
        self.changed.set()

    def status(self):
        return {
            "type": "status",
            "legs": self.legs,
            "players": {role: len(ws) for role, ws in self.players.items()},
        }


# ---------------------------- robot connections ----------------------------
class DryRunRobot:
    async def connect(self):
        print("Dry run: no robot connected, commands are printed instead.")

    async def send(self, text):
        print("->", text)


class SerialRobot:
    def __init__(self, port):
        self.port = port

    async def connect(self):
        import serial  # pyserial

        self.serial = serial.Serial(self.port, 115200, timeout=0.1)
        await asyncio.sleep(2)  # the board may reset when the port opens
        threading.Thread(target=self._print_replies, daemon=True).start()
        print(f"Connected to the Bittle on {self.port}")

    def _print_replies(self):
        while True:
            line = self.serial.readline()
            if line:
                print("<-", line.decode(errors="replace").rstrip())

    async def send(self, text):
        self.serial.write((text + "\n").encode())


class BleRobot:
    def __init__(self, name_part):
        self.name_part = (name_part or "").lower()

    async def connect(self):
        from bleak import BleakClient, BleakScanner

        print("Looking for the Bittle over Bluetooth...")
        found = await BleakScanner.discover(timeout=8, return_adv=True)
        matches = [
            device
            for device, adv in found.values()
            if ble_service.lower() in [u.lower() for u in adv.service_uuids]
            or (device.name and "_ble" in device.name.lower())
        ]
        if self.name_part:
            matches = [d for d in matches if d.name and self.name_part in d.name.lower()]
        if not matches:
            raise SystemExit(
                "No Bittle found. Is it switched on, and disconnected from the phone app?"
            )
        device = matches[0]
        self.client = BleakClient(device)
        await self.client.connect()
        char = self.client.services.get_characteristic(ble_rx_char)
        self.chunk = max(20, char.max_write_without_response_size)
        print(f"Connected to {device.name} over Bluetooth")

    async def send(self, text):
        data = (text + "\n").encode()
        for start in range(0, len(data), self.chunk):
            await self.client.write_gatt_char(
                ble_rx_char, data[start:start + self.chunk], response=False
            )


class StudioRobot:
    """The simulated Bittle in Bittle Studio. Start the Studio first; its servo
    settings (Servo setup) translate the robot's joint numbers to the 3D model."""

    def __init__(self, url):
        self.url = url.rstrip("/")
        # talk to the Studio directly, never through a proxy or VPN set up in Windows
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _call(self, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.url + path, data, {"Content-Type": "application/json"})
        with self.opener.open(request, timeout=30) as response:
            return json.load(response)

    async def connect(self):
        try:
            model = await asyncio.to_thread(self._call, "/api/model")
        except OSError as error:
            raise SystemExit(
                f"Can't reach Bittle Studio at {self.url}: {error}\n"
                "Is it running (Start Bittle Studio)? If it uses another address, pass it: --studio http://127.0.0.1:PORT"
            )
        self.joints = {m["servo"]: (name, m["sign"], m.get("offset", 0)) for name, m in model["mapping"].items()}
        await asyncio.to_thread(self._call, "/api/command", {"action": "run", "value": True})
        print(f"Connected to Bittle Studio at {self.url} (physics is now running)")

    async def send(self, text):
        parts = text.split()
        if parts[0] != "i":  # the simulator only needs the joint angles
            return
        pose = {}
        for servo, angle in zip(parts[1::2], parts[2::2]):
            if int(servo) in self.joints:
                name, sign, offset = self.joints[int(servo)]
                pose[name] = (float(angle) - offset) * sign
        await asyncio.to_thread(self._call, "/api/command", {"action": "pose", "pose": pose})


async def robot_loop(game, robot):
    await robot.connect()
    for cmd in START_COMMANDS:
        await robot.send(cmd)
        await asyncio.sleep(0.3)
    last = None
    game.changed.set()  # send the starting stance right away
    while True:
        await game.changed.wait()
        game.changed.clear()
        cmd = game.command()
        if cmd != last:
            await robot.send(cmd)
            last = cmd
        await asyncio.sleep(1 / SEND_RATE_HZ)


# ------------------------------- web server --------------------------------
async def broadcast(game):
    message = json.dumps(game.status())
    for sockets in game.players.values():
        for ws in list(sockets):
            try:
                await ws.send_str(message)
            except ConnectionError:
                pass


async def websocket(request):
    game = request.app["game"]
    ws = web.WebSocketResponse(heartbeat=10)
    await ws.prepare(request)
    role = None
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            data = json.loads(msg.data)
            if data.get("type") == "join" and data.get("role") in ROLES:
                if role:
                    game.players[role].discard(ws)
                role = data["role"]
                game.players[role].add(ws)
                print(f"A player joined as {role}")
            elif data.get("type") == "leg" and role:
                name = data.get("leg")
                if name in ROLES[role]:
                    game.legs[name]["swing"] = clamp(float(data.get("swing", 0)), -1, 1)
                    game.legs[name]["lift"] = clamp(float(data.get("lift", 0)), 0, 1)
                    game.changed.set()
            elif data.get("type") == "reset":
                game.reset()
            await broadcast(game)
    finally:
        if role:
            game.players[role].discard(ws)
            for name in ROLES[role]:  # put the leaving player's feet down
                game.legs[name]["lift"] = 0.0
            game.changed.set()
            print(f"A player left ({role})")
            await broadcast(game)
    return ws


async def index(request):
    return web.FileResponse(STATIC / "index.html")


def local_ips():
    """All IPv4 addresses of this laptop; the one used for internet comes first."""
    ips = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
        except OSError:
            pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except OSError:
        pass
    return ips or ["127.0.0.1"]


async def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    link = parser.add_mutually_exclusive_group(required=True)
    link.add_argument("--serial", metavar="PORT", help="USB serial port, e.g. COM5 or /dev/ttyUSB0")
    link.add_argument("--ble", nargs="?", const="", metavar="NAME", help="connect over Bluetooth (optionally part of the robot's name)")
    link.add_argument("--studio", nargs="?", const="http://127.0.0.1:8765", metavar="URL", help="drive the simulated Bittle in Bittle Studio")
    link.add_argument("--dry-run", action="store_true", help="no robot, print the commands")
    parser.add_argument("--port", type=int, default=8080, help="web server port (default 8080)")
    args = parser.parse_args()

    if args.serial:
        robot = SerialRobot(args.serial)
    elif args.studio:
        robot = StudioRobot(args.studio)
    elif args.ble is not None:
        robot = BleRobot(args.ble)
    else:
        robot = DryRunRobot()

    game = Game()
    app = web.Application()
    app["game"] = game
    app.router.add_get("/", index)
    app.router.add_get("/ws", websocket)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", args.port).start()
    print(f"\nTest it on this laptop first:  http://localhost:{args.port}")
    print("Then open one of these on both phones (same WiFi as this laptop):")
    for ip in local_ips():
        print(f"    http://{ip}:{args.port}")
    print("If the first one shows something else, try the next. Use the one that says 'Bittle Duo'.\n")

    await robot_loop(game, robot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
