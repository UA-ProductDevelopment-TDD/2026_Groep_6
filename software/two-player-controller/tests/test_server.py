"""Checks that the phone page and the server still work together.

Run from software/two-player-controller:
    python -m unittest discover -s tests -v
"""

import asyncio
import json
import sys
import unittest
from pathlib import Path

from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: E402

# Servo limits of the Bittle legs, from angleLimit in software/arduino/src/OpenCat.h (BITTLE).
SERVO_LIMITS = {
    8: (-200, 80), 9: (-200, 80), 10: (-80, 200), 11: (-80, 200),     # shoulders
    12: (-80, 200), 13: (-80, 200), 14: (-80, 200), 15: (-80, 200),   # knees
}


class PageAndServerTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.game = server.Game()
        self.client = TestClient(TestServer(server.make_app(self.game)))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()

    async def receive_status(self, ws):
        msg = await asyncio.wait_for(ws.receive_json(), timeout=2)
        self.assertEqual(msg["type"], "status")
        return msg

    async def test_page_loads(self):
        response = await self.client.get("/")
        self.assertEqual(response.status, 200)
        self.assertIn("Bittle Duo", await response.text())

    async def test_roles_are_sent_right_after_connecting(self):
        # the role buttons on the page stay off until this first status arrives
        ws = await self.client.ws_connect("/ws")
        status = await self.receive_status(ws)
        self.assertEqual(status["roles"], server.ROLES)
        await ws.close()

    async def test_every_role_can_join_and_move_its_legs(self):
        for role, legs in server.ROLES.items():
            with self.subTest(role=role):
                self.game.reset()
                ws = await self.client.ws_connect("/ws")
                await self.receive_status(ws)  # the status sent on connect
                await ws.send_str(json.dumps({"type": "join", "role": role}))
                status = await self.receive_status(ws)
                self.assertEqual(status["roles"], server.ROLES)  # the page reads the legs from here
                self.assertEqual(status["players"][role], 1)
                for leg in legs:
                    await ws.send_str(json.dumps({"type": "leg", "leg": leg, "swing": 0.5, "lift": 1}))
                    status = await self.receive_status(ws)
                    self.assertEqual(status["legs"][leg], {"swing": 0.5, "lift": 1.0})
                # a leg that belongs to the partner is ignored
                other = next(leg for leg in server.LEGS if leg not in legs)
                await ws.send_str(json.dumps({"type": "leg", "leg": other, "swing": 1, "lift": 1}))
                status = await self.receive_status(ws)
                self.assertEqual(status["legs"][other], {"swing": 0.0, "lift": 0.0})
                await ws.close()


class LegAnglesTest(unittest.TestCase):
    def test_angles_stay_within_servo_limits(self):
        steps = [i / 10 for i in range(-10, 11)]
        for style in server.LEG_STYLES:
            game = server.Game(legs=style)
            for swing in steps:
                for lift in (0, 0.3, 0.5, 1):
                    for name in server.LEGS:
                        game.legs[name] = {"swing": swing, "lift": lift}
                    parts = game.command().split()
                    self.assertEqual(parts[0], "i")
                    for joint, angle in zip(parts[1::2], parts[2::2]):
                        low, high = SERVO_LIMITS[int(joint)]
                        with self.subTest(style=style, swing=swing, lift=lift, joint=joint):
                            self.assertTrue(low <= int(angle) <= high, f"{angle} outside {low}..{high}")

    def test_lifting_folds_the_knee(self):
        for style, leg_angles in server.LEG_STYLES.items():
            for name in server.LEGS:
                for swing in (-1, 0, 1):
                    with self.subTest(style=style, leg=name, swing=swing):
                        _, knee_down = leg_angles(name, swing, 0)
                        _, knee_up = leg_angles(name, swing, 1)
                        self.assertLess(knee_up, knee_down)

    def test_default_is_simple(self):
        self.assertIs(server.Game().leg_angles, server.leg_angles)


if __name__ == "__main__":
    unittest.main()
