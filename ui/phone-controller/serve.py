"""Try the new phone page with the real two-player server.

This reuses software/two-player-controller/server.py as it is (same game logic,
same robot connections) and only swaps in the phone page from this folder.

Run from this folder, with the same options as server.py:
    python serve.py --dry-run          (no robot)
    python serve.py --studio           (Bittle Studio)
    python serve.py --serial COM3      (USB)
    python serve.py --ble              (Bluetooth)
"""

import asyncio
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "software" / "two-player-controller"))

import server  # noqa: E402

server.STATIC = HERE  # serve index.html from ui/phone-controller instead of static/

if __name__ == "__main__":
    try:
        asyncio.run(server.main())
    except KeyboardInterrupt:
        pass
