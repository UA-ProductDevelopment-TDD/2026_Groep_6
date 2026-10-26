# Bittle Duo: two-player leg controller

Two people steer one Bittle, each controlling two legs from their own phone. The dog only walks if you work together.

```
phone (left legs) ──┐   WiFi   ┌── laptop: server.py ── USB or Bluetooth ──> Bittle
phone (right legs) ─┘          └── (merges both players and sends joint angles)
```

The robot's firmware stays as it is. The laptop sends standard OpenCat commands (`i` = move joints, `gb` = gyro balancing off).

## Setup (once)

1. Install Python 3.10 or newer.
2. In this folder, run:
   ```
   pip install -r requirements.txt
   ```

## Run

1. Switch the Bittle on and put it on the floor, standing.
2. Start the server on the laptop. Pick one way to connect:
   - **USB cable:** `python server.py --serial COM5`. Find the COM port in Arduino IDE or Device Manager.
   - **Bluetooth:** `python server.py --ble`. First close the Petoi app on your phone, because the robot accepts only one Bluetooth connection at a time. If several Bittles are nearby, add part of the name: `--ble Bittle12`.
   - **The simulated Bittle in Bittle Studio:** first start the Studio (`launchers/windows/Start Bittle Studio`), then run `python server.py --studio`. This turns the Studio's physics on and the 3D Bittle follows the phones. It's a safe way to practise before using the real robot. Press **Follow** above the 3D view so the camera keeps the dog in view. If you press **Reset** in the Studio, press **Run physics** again afterwards.
   - **No robot, just testing the page:** `python server.py --dry-run`
3. The server prints an address like `http://192.168.1.23:8080`. Open it on both phones. The phones need to be on the **same WiFi as the laptop**. The first time, Windows asks to let Python through the firewall. Click Allow.
4. Pick a split and take one role each:
   - **Left / right:** LEFT has both left legs and RIGHT has both right legs.
   - **Front / back:** FRONT has both front legs and BACK has both back legs.
   - **Diagonal** (the way a chameleon walks): DIAGONAL 1 has left front and right back, and DIAGONAL 2 has right front and left back.

> University WiFi (eduroam) often blocks devices from talking to each other. If the phones can't open the page, turn on the laptop's **mobile hotspot** and connect both phones to it.

## How to play

Each phone has two pads, one for each of your legs. You can use one thumb on each.

- **Hold a pad and slide sideways** to lift the foot (the dot turns green).
- **Slide up or down** to swing the leg forward or back.
- **Let go** to put the foot down. The leg stays where you left it.
- Moving a leg back while its foot is down pushes the dog forward.

A walking hint: Bittle walks by moving diagonal pairs of legs together. So the left front leg goes with the right back leg, and the right front leg goes with the left back leg. In the diagonal split, each player moves their own two legs together. In the other splits, you have to time your moves with your partner's. Call out the rhythm to each other.

The little dog at the top of the screen shows all four legs, including your partner's. **Reset legs** puts all four feet down in the middle.

## Tuning

All the numbers are at the top of `server.py`:

| Setting | What it does |
|---|---|
| `FRONT` / `BACK` `center`, `range` | Shoulder angle in the middle, and how far a full swing goes |
| `knee_slope` | How much the knee bends as the leg swings back, so the body stays level |
| `LIFT_DEGREES` | How high the stepping foot is lifted |
| `SEND_RATE_HZ` | How often the robot gets new angles. Lower it if the robot stutters over Bluetooth |
| `START_COMMANDS` | Sent once at the start. `gb` turns off gyro balancing |

The defaults come from Bittle's own walking gait in the OpenCat firmware. They haven't been tested on a real robot yet. If a leg moves the wrong way or too far, change these numbers first. Start with small moves. If the robot falls over and tries to stand back up on its own, that's the firmware's fall recovery.

## Tested in Bittle Studio

The `--studio` connection was tested against the Studio's physics simulation. An earlier one-slider-per-side version walked the simulated Bittle about 40 to 47 cm forward in 10 to 16 seconds.

## Files

- `server.py`: the laptop server (web page, game logic, robot connection)
- `static/index.html`: the phone page
- `requirements.txt`: Python packages
