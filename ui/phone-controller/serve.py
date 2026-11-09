"""Try the new phone page with the real two-player server.

This reuses software/two-player-controller/server.py (same game logic, same
robot connections), swaps in the phone page from this folder, and tries out a
more natural leg movement where the elbow/knee moves along with the shoulder.

Run from the repo folder, with the same options as server.py:
    python ui/phone-controller/serve.py --dry-run          (no robot)
    python ui/phone-controller/serve.py --studio           (Bittle Studio)
    python ui/phone-controller/serve.py --serial COM3      (USB)
    python ui/phone-controller/serve.py --ble              (Bluetooth)
Add --old-legs to get the original leg movement from server.py, to compare.
"""

import asyncio
import sys
from bisect import bisect_left
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "software" / "two-player-controller"))

import server  # noqa: E402

server.STATIC = HERE  # serve index.html from ui/phone-controller instead of static/

# --------------------------------------------------------------------------
# Natural leg movement (experiment, not yet in server.py).
#
# The knee curves below are read from Bittle's own walking gait (wkF in
# software/arduino/src/InstinctBittleESP.h), as (shoulder angle, knee angle):
#  - DOWN: foot on the floor. The knee straightens at the front and the back of
#    the step and bends a bit in the middle, so the foot stays on the floor.
#  - UP:   foot in the air. The knee folds most in the middle of the swing and
#    reaches out again at the front to put the foot down.
# Shoulder: smaller angle = foot forward. Knee: smaller angle = leg more folded.
# --------------------------------------------------------------------------
NATURAL = {
    "F": {  # front legs (the "elbows")
        "down": [(13, 14), (19, 11), (26, 7), (32, 4), (38, 2), (44, 1), (50, 4),
                 (56, 6), (60, 11), (64, 20), (70, 26)],
        "up":   [(13, 14), (17, 6), (21, 1), (26, -2), (34, -6), (41, -9), (54, -9),
                 (60, -7), (64, -3), (70, 6)],
    },
    "B": {  # back legs (the knees)
        "down": [(22, 11), (27, 8), (33, 6), (39, 3), (49, 3), (55, 5), (61, 8),
                 (64, 14), (70, 22), (74, 28)],
        "up":   [(22, 11), (26, 3), (31, -2), (40, -5), (47, -7), (54, -9), (60, -7),
                 (65, -5), (68, -1), (74, 8)],
    },
}
EXTRA_LIFT = 15  # degrees of extra fold when the foot is fully up, so lifting is easy to see


def curve(points, x):
    """Straight-line interpolation between the (x, y) points; flat beyond the ends."""
    xs = [p[0] for p in points]
    if x <= xs[0]:
        return points[0][1]
    if x >= xs[-1]:
        return points[-1][1]
    i = bisect_left(xs, x)
    (x0, y0), (x1, y1) = points[i - 1], points[i]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def natural_leg_angles(name, swing, lift):
    """swing: -1 (back) .. +1 (forward), lift: 0 (planted) .. 1 (up)."""
    cfg = server.FRONT if name[0] == "F" else server.BACK
    shoulder = cfg["center"] - server.clamp(swing, -1, 1) * cfg["range"]
    lift = server.clamp(lift, 0, 1)
    knees = NATURAL[name[0]]
    down, up = curve(knees["down"], shoulder), curve(knees["up"], shoulder)
    knee = down + lift * (up - down) - lift * EXTRA_LIFT
    return round(shoulder), round(knee)


if __name__ == "__main__":
    if "--old-legs" in sys.argv:
        sys.argv.remove("--old-legs")
        print("Using the original leg movement from server.py")
    else:
        server.leg_angles = natural_leg_angles
        print("Using the natural leg movement from ui/phone-controller/serve.py")
    try:
        asyncio.run(server.main())
    except KeyboardInterrupt:
        pass
