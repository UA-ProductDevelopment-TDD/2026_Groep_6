# Phone controller (redesign)

A new design for the **Bittle Duo** phone page (the two-player controller from `software/two-player-controller/`).
It talks to the same `server.py` with exactly the same messages, so nothing in `software/` has to change to try it.

## What's new compared to the old page

- **Role picker:** every split has a small dog drawing showing which legs each role gets, and a "1 playing" badge on roles someone already took.
- **Status pill:** green = connected and partner is here, yellow = waiting for partner, red = lost the laptop.
- **Bigger pads:** a "foot down / foot lifted" label, a bar that shows how far the leg is swung, and the whole pad lights up green while the foot is lifted.
- **Vibration** when the foot lifts or touches down (Android; iPhones don't allow it).
- **Screen stays on** while you play, where the browser allows it.
- **Landscape:** turn the phone sideways to get one pad per thumb with the dog in the middle.

## Try it

You need the same Python packages as the server (`pip install -r ../../software/two-player-controller/requirements.txt`).
Then, in this folder:

```
python serve.py --dry-run
```

`serve.py` starts the normal `server.py` but serves the page from this folder. It takes the same options:
`--studio`, `--serial COM3`, `--ble`. Open the address it prints on the phones, just like in `software/INSTRUCTIES.md`.

## Using it for real

When the team likes it, the software pair can copy `index.html` over `software/two-player-controller/static/index.html`.
If someone changes the roles or messages in `server.py`, the `ROLES` list at the top of the script in `index.html` must change too.
