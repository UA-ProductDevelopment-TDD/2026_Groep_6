"""Checks that the phone page and the server still work together.

Run from software/two-player-controller:
    python -m unittest discover -s tests -v
"""

import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: E402

# Servo limits of the Bittle legs, from angleLimit in software/arduino/src/OpenCat.h (BITTLE).
SERVO_LIMITS = {
    0: (-120, 120),                                                    # head
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

    async def test_horizontal_page_and_app_files_load(self):
        response = await self.client.get("/horizontal")
        self.assertEqual(response.status, 200)
        page = await response.text()
        self.assertIn("BITE", page)
        self.assertIn('rel="manifest"', page)
        response = await self.client.get("/manifest.webmanifest")
        self.assertEqual(response.status, 200)
        manifest = json.loads(await response.text())
        self.assertEqual(manifest["start_url"], "/horizontal")
        for icon in manifest["icons"]:
            with self.subTest(icon=icon["src"]):
                response = await self.client.get(icon["src"])
                self.assertEqual(response.status, 200)
                self.assertEqual(response.content_type, "image/png")
        response = await self.client.get("/sw.js")
        self.assertEqual(response.status, 200)
        self.assertIn("javascript", response.content_type)

    async def test_status_sends_the_angles_the_robot_gets(self):
        # the horizontal page draws the legs from these, so it needs no copy of the formula
        self.game.legs["FL"] = {"swing": 0.5, "lift": 1.0}
        ws = await self.client.ws_connect("/ws")
        status = await self.receive_status(ws)
        for name, leg in self.game.legs.items():
            self.assertEqual(status["angles"][name], list(self.game.leg_angles(name, **leg)))
        await ws.close()

    async def latest_status(self, ws):
        """The newest status, skipping older ones that other players' moves sent to this phone too."""
        status = await self.receive_status(ws)
        while True:
            try:
                status = await asyncio.wait_for(ws.receive_json(), timeout=0.1)
            except asyncio.TimeoutError:
                return status

    async def join(self, role):
        ws = await self.client.ws_connect("/ws")
        await ws.send_str(json.dumps({"type": "join", "role": role}))
        await self.latest_status(ws)
        return ws

    async def bite(self, ws, pressed=True):
        await ws.send_str(json.dumps({"type": "bite", "pressed": pressed}))
        return await self.latest_status(ws)

    async def test_bite_alone_does_nothing(self):
        front = await self.join("front")
        await self.join("back")
        status = await self.bite(front)
        self.assertEqual(status["bite"]["pressed"], ["front"])
        self.assertFalse(status["bite"]["active"])
        self.assertFalse(self.game.head_used)
        self.assertEqual(self.game.command().split()[1], "8")  # no head in the command yet

    async def test_bite_together_sweeps_the_head(self):
        quick = [(0, 0.0), (-120, 0.1), (120, 0.2), (0, 0.3)]
        with mock.patch.object(server, "HEAD_SPIN", quick), mock.patch.object(server, "BITE_COOLDOWN_S", 0.1):
            front, back = await self.join("front"), await self.join("back")
            await self.bite(front)
            await self.bite(back)
            self.assertTrue(self.game.spinning)
            self.assertEqual(self.game.pending, server.BITE_EXTRA_COMMANDS)
            self.assertEqual(self.game.command().split()[1], str(server.HEAD_JOINT))
            # pressing again during the sweep does not start a second one
            self.assertFalse(self.game.press_bite(object(), "front", True, self._noop))
            await asyncio.sleep(0.5)
            self.assertFalse(self.game.spinning)
            self.assertEqual(self.game.head, 0)
            self.assertEqual(self.game.command().split()[1:3], [str(server.HEAD_JOINT), "0"])

    async def test_partner_tapping_shortly_after_also_counts(self):
        front, back = await self.join("front"), await self.join("back")
        await self.bite(front)
        await self.bite(front, pressed=False)  # a quick tap...
        await self.bite(back)                  # ...and the partner taps right after
        self.assertTrue(self.game.spinning)

    @staticmethod
    async def _noop():
        pass


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

    def test_head_sweep_uses_the_whole_range_and_ends_in_the_middle(self):
        end = server.HEAD_SPIN[-1][1]
        angles = [server.head_angle_at(end * i / 200) for i in range(201)]
        self.assertEqual(min(angles), server.HEAD_LIMITS[0])
        self.assertEqual(max(angles), server.HEAD_LIMITS[1])
        self.assertEqual(angles[0], 0)
        self.assertEqual(angles[-1], 0)

    def test_head_stays_within_its_servo_limits(self):
        game = server.Game()
        game.head_used = True
        for head in (-500, -120, 0, 120, 500):
            game.head = head
            angle = int(game.command().split()[2])
            low, high = SERVO_LIMITS[0]
            self.assertTrue(low <= angle <= high, f"{angle} outside {low}..{high}")


if __name__ == "__main__":
    unittest.main()
