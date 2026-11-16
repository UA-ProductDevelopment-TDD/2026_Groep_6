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

## The phone page

The page is `static/index.html`. The UI pair designs it there. It has:

- **Role picker:** every split has a small dog drawing showing which legs each role gets, and a "1 playing" badge on roles someone already took. Which legs belong to a role comes from `ROLES` in `server.py`; the page only has the labels and colours.
- **Status pill:** green = connected and partner is here, yellow = waiting for partner, red = lost the laptop.
- **Pads:** a "foot down / foot lifted" label, a bar that shows how far the leg is swung, and the pad lights up green while the foot is lifted.
- **Vibration** when the foot lifts or touches down (Android; iPhones don't allow it).
- **Screen stays on** while you play, but only on `https://` or `localhost`. The phones open `http://<laptop IP>`, where browsers don't allow it, so the page shows a tip to set the screen timeout longer instead.
- **Landscape:** turn the phone sideways to get one pad per thumb with the dog in the middle.

## How to play

Each phone has two pads, one for each of your legs. You can use one thumb on each.

- **Hold a pad and slide sideways** to lift the foot (the dot turns green).
- **Slide up or down** to swing the leg forward or back.
- **Let go** to put the foot down. The leg stays where you left it.
- Moving a leg back while its foot is down pushes the dog forward.

A walking hint: Bittle walks by moving diagonal pairs of legs together. So the left front leg goes with the right back leg, and the right front leg goes with the left back leg. In the diagonal split, each player moves their own two legs together. In the other splits, you have to time your moves with your partner's. Call out the rhythm to each other.

The little dog at the top of the screen shows all four legs, including your partner's. **Reset legs** puts all four feet down in the middle.

## Horizontal version: sliders and BITE (`/horizontal`)

A landscape page for the front / back split, made by the UI pair. Open `http://<laptop IP>:8080/horizontal` (or tap the link under the role picker) and hold the phone sideways.

- One player picks **FRONT LEGS**, the other **BACK LEGS**.
- Each side of the screen is one leg (left side = the dog's left leg) with two sliders: **Swing** (outer edge) moves the leg forward/back and stays where you leave it, **Lift** (inner edge) raises the foot and drops back down when you let go (`LIFT_SPRINGS_BACK` in the page).
- The middle shows a **live side view** of the chameleon Bittle. The server sends the joint angles it gives the robot (`angles` in the status), so the drawing follows `--legs` and needs no copy of the formula. Your legs are bright, your partner's faded.
- **BITE** only works when **both players press together** (within `BITE_WINDOW_S`, or while the other is still holding). Then the robot beeps and the head servo sweeps through its whole range: all the way to one side, all the way to the other, and back to the middle (about 3 s). A dial in the drawing shows where the head points. It's a test of the servo before the head is rebuilt into the chameleon's tongue.

A full 360° turn isn't possible: a normal servo can't spin round, and the firmware limits the Bittle's head to -120..+120° (`angleLimit` in `software/arduino/src/OpenCat.h`). In Bittle Studio the 3D head stops at ±90°, the limit of the 3D model.
The head only joins the `i` command after the first BITE, so nothing changes for players on the portrait page.

### Install it as an app on the phone

`/horizontal` can be put on the home screen as an app: chameleon icon, fullscreen, and (on Android) locked to landscape. The laptop server must still be running.

- **Android (Chrome):** Chrome only installs apps from secure sites, and the laptop is plain `http://`. So first open `chrome://flags`, search **Insecure origins treated as secure**, type the laptop address (e.g. `http://192.168.43.127:8080`, without `/horizontal`), set it to **Enabled** and tap **Relaunch**. Then open `/horizontal`, tap **⋮** > **Add to home screen** > **Install** (not "Create shortcut").
- **iPhone (Safari):** open `/horizontal`, tap **Share** > **Add to Home Screen**. iPhones can't lock the direction, so hold the phone sideways.

The app remembers the laptop address. If the laptop gets another address, delete the app and install it again.

## Tuning

All the numbers are at the top of `server.py`:

| Setting | What it does |
|---|---|
| `FRONT` / `BACK` `center`, `range` | Shoulder angle in the middle, and how far a full swing goes |
| `knee_slope` | How much the knee bends as the leg swings back, so the body stays level |
| `LIFT_DEGREES` | How high the stepping foot is lifted |
| `SEND_RATE_HZ` | How often the robot gets new angles. Lower it if the robot stutters over Bluetooth |
| `START_COMMANDS` | Sent once at the start. `gb` turns off gyro balancing |
| `NATURAL`, `EXTRA_LIFT` | Knee curves and lift for `--legs natural` (see below) |
| `HEAD_JOINT`, `HEAD_SPIN` | Which servo BITE sweeps (0 = head; later the tongue servo) and the sweep as (angle, seconds) points. Use smaller angles to test carefully first |
| `BITE_EXTRA_COMMANDS` | Sent when BITE starts (default a beep, `[]` for silence) |
| `BITE_WINDOW_S`, `BITE_COOLDOWN_S` | How close together the two presses must be, and the rest time after a sweep |

The defaults come from Bittle's own walking gait in the OpenCat firmware. They haven't been tested on a real robot yet. If a leg moves the wrong way or too far, change these numbers first. Start with small moves. If the robot falls over and tries to stand back up on its own, that's the firmware's fall recovery.

## Natural leg movement (`--legs natural`, experiment)

By default (`--legs simple`) the knee (on the front legs: the elbow) moves a little in a straight line with the shoulder, and folds 35° when the foot is lifted.
With `--legs natural`, the knee follows curves based on Bittle's own walking gait (`wkF` in `software/arduino/src/InstinctBittleESP.h`):

- **Foot on the floor:** the knee is bent when the leg is at the front and straightens as the leg moves back, so the leg pushes the dog forward.
- **Foot lifted:** the knee folds most in the middle of the swing and reaches out again at the front to put the foot down.

For example: `python server.py --studio --legs natural`. The numbers are in `NATURAL` and `EXTRA_LIFT` in `server.py`.

In Bittle Studio, with a diagonal pattern, the dog walks forward with no lift (about 13 cm), a little lift (about 34 cm) and a full lift (about 29 cm), in 4 steps.
**Not tested on the real robot yet.** The lift is weaker than with `simple` (about 15 to 25° of extra fold instead of 35°), so check that the feet clear the floor before making it the default.

## Test

After changing the page or `server.py`, run the automatic test in this folder:

```
python -m unittest discover -s tests -v
```

It checks that the page loads, that every role can join and move only its own legs, that the server sends the roles to the page, and that both leg styles stay within the Bittle's servo limits. For the horizontal page it checks that the page and app files load, that BITE alone does nothing, that BITE together sweeps the head through its whole range and back to 0, and that the head stays within its servo limits. It needs no robot. Then start `python server.py --dry-run` and check on a phone (or in a browser) that the pads move.

## Tested in Bittle Studio

The `--studio` connection was tested against the Studio's physics simulation. An earlier one-slider-per-side version walked the simulated Bittle about 40 to 47 cm forward in 10 to 16 seconds.

## Files

- `server.py`: the laptop server (web page, game logic, leg movement, robot connection)
- `static/index.html`: the phone page
- `static/horizontal.html`: the landscape page with sliders, live side view and BITE
- `static/manifest.webmanifest`, `static/sw.js`, `static/icons/`: make `/horizontal` installable as an app
- `tests/test_server.py`: the automatic test
- `requirements.txt`: Python packages
