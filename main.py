# NOTE: This app is a lightweight endless-runner style prototype.
# It uses Panda3D for a simple 3D runner (3 lanes, jump, obstacles, score).
# Controls: Left/Right arrows (lane switch), Space (jump), R (restart), Esc (quit)
# This file is intended to be packaged to EXE via PyInstaller.

from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    AmbientLight, DirectionalLight, Vec3, Vec4,
    CardMaker, NodePath, TextNode, LVector3f
)
from direct.task import Task
from direct.gui.OnscreenText import OnscreenText
import random
import math
import time

LANES = [-2.2, 0.0, 2.2]

class RunnerGame(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)
        self.disableMouse()
        self.setBackgroundColor(0.55, 0.8, 1.0, 1)

        # Window title
        try:
            self.win.setTitle("Cartoon Runner 3D")
        except Exception:
            pass

        self._setup_lights()
        self._setup_ui()
        self._setup_world()
        self._setup_player()

        self.accept("escape", self.userExit)
        self.accept("arrow_left", self.move_left)
        self.accept("arrow_right", self.move_right)
        self.accept("space", self.jump)
        self.accept("r", self.restart)

        self.restart()
        self.taskMgr.add(self.update, "update")

    def _setup_lights(self):
        amb = AmbientLight("amb")
        amb.setColor(Vec4(0.65, 0.65, 0.7, 1))
        amb_np = self.render.attachNewNode(amb)
        self.render.setLight(amb_np)

        d = DirectionalLight("dir")
        d.setColor(Vec4(0.9, 0.9, 0.85, 1))
        d_np = self.render.attachNewNode(d)
        d_np.setHpr(45, -45, 0)
        self.render.setLight(d_np)

    def _setup_ui(self):
        self.score_text = OnscreenText(
            text="Score: 0",
            pos=(-1.3, 0.9),
            scale=0.06,
            fg=(0.05, 0.05, 0.08, 1),
            align=TextNode.ALeft,
            mayChange=True,
        )
        self.hint_text = OnscreenText(
            text="←/→: voies   Espace: saut   R: restart",
            pos=(0, -0.93),
            scale=0.05,
            fg=(0.05, 0.05, 0.08, 1),
            align=TextNode.ACenter,
            mayChange=True,
        )
        self.gameover_text = OnscreenText(
            text="",
            pos=(0, 0.1),
            scale=0.1,
            fg=(0.85, 0.15, 0.18, 1),
            align=TextNode.ACenter,
            mayChange=True,
        )

    def _setup_world(self):
        # Ground as repeating cards (cartoon colors)
        self.ground_tiles = []
        cm = CardMaker("ground")
        cm.setFrame(-7, 7, -7, 7)

        for i in range(6):
            tile = self.render.attachNewNode(cm.generate())
            tile.setP(-90)
            tile.setPos(0, 0 + i * 14, 0)
            # alternating greens
            c = (0.35, 0.85, 0.45, 1) if i % 2 == 0 else (0.28, 0.75, 0.4, 1)
            tile.setColor(*c)
            self.ground_tiles.append(tile)

        # Simple lane markings
        self.lane_markers = []
        cm2 = CardMaker("marker")
        cm2.setFrame(-0.05, 0.05, -7, 7)
        for x in [(-1.1), (1.1)]:
            for i in range(8):
                m = self.render.attachNewNode(cm2.generate())
                m.setP(-90)
                m.setPos(x, i * 10, 0.01)
                m.setColor(1, 1, 1, 0.7)
                self.lane_markers.append(m)

        # Camera
        self.camera.setPos(0, -16, 7.5)
        self.camera.lookAt(0, 12, 1.2)

    def _setup_player(self):
        # Player: a colorful "capsule" using built-in models
        # panda-models typically include "smiley" or "box" depending on install.
        # We'll assemble a player from primitives:
        self.player = self.render.attachNewNode("player")
        self.player_model = self.loader.loadModel("models/misc/rgbCube")
        self.player_model.reparentTo(self.player)
        self.player_model.setScale(0.6, 0.9, 1.0)
        self.player_model.setColor(0.9, 0.35, 0.25, 1)
        self.player.setPos(LANES[1], 0, 1.0)

        self.lane_index = 1
        self.player_y = 0.0
        self.player_z = 1.0
        self.vz = 0.0
        self.on_ground = True

        # Simple shadow
        cm = CardMaker("shadow")
        cm.setFrame(-0.5, 0.5, -0.5, 0.5)
        self.shadow = self.render.attachNewNode(cm.generate())
        self.shadow.setP(-90)
        self.shadow.setColor(0, 0, 0, 0.25)
        self.shadow.setPos(self.player.getX(), self.player.getY(), 0.02)

    def restart(self):
        self.game_over = False
        self.time_start = time.time()
        self.score = 0
        self.speed = 18.0
        self.speed_increase = 0.6  # per 10 seconds approx

        self.lane_index = 1
        self.player_y = 0.0
        self.player_z = 1.0
        self.vz = 0.0
        self.on_ground = True
        self.player.setPos(LANES[self.lane_index], self.player_y, self.player_z)
        self.gameover_text.setText("")

        # Obstacles
        if hasattr(self, "obstacles"):
            for ob in self.obstacles:
                ob.removeNode()
        self.obstacles = []

        # spawn initial obstacles ahead
        for i in range(8):
            self._spawn_obstacle(y=35 + i * 18)

    def _spawn_obstacle(self, y=None):
        lane = random.randint(0, 2)
        if y is None:
            y = 120 + random.random() * 40

        ob = self.render.attachNewNode("ob")
        m = self.loader.loadModel("models/misc/rgbCube")
        m.reparentTo(ob)

        # Cartoon-ish obstacle colors
        palette = [
            (0.2, 0.35, 0.95, 1),
            (0.95, 0.85, 0.25, 1),
            (0.6, 0.25, 0.95, 1),
            (0.2, 0.8, 0.85, 1),
        ]
        m.setColor(*random.choice(palette))

        kind = random.choice(["low", "high"])
        if kind == "low":
            m.setScale(0.95, 0.95, 1.15)
            z = 0.6
            h = 1.15
            requires_jump = True
        else:
            m.setScale(0.95, 0.95, 0.85)
            z = 1.8
            h = 0.85
            requires_jump = False

        ob.setPos(LANES[lane], y, z)
        ob.setTag("lane", str(lane))
        ob.setPythonTag("h", h)
        ob.setPythonTag("requires_jump", requires_jump)
        self.obstacles.append(ob)

    def move_left(self):
        if self.game_over:
            return
        self.lane_index = max(0, self.lane_index - 1)

    def move_right(self):
        if self.game_over:
            return
        self.lane_index = min(2, self.lane_index + 1)

    def jump(self):
        if self.game_over:
            return
        if self.on_ground:
            self.on_ground = False
            self.vz = 9.5

    def _collides(self, ob):
        # AABB-ish in lane and distance
        dx = abs(ob.getX() - self.player.getX())
        dy = abs(ob.getY() - self.player.getY())
        if dx > 0.9 or dy > 1.2:
            return False
        # vertical overlap
        ob_h = ob.getPythonTag("h")
        ob_z = ob.getZ()
        pz = self.player.getZ()
        # player height about 2
        if (pz - 0.9) > (ob_z + ob_h):
            return False
        if (pz + 1.0) < (ob_z - ob_h):
            return False
        return True

    def update(self, task):
        dt = globalClock.getDt()
        if dt > 0.05:
            dt = 0.05

        # Smooth lane movement
        target_x = LANES[self.lane_index]
        cur = self.player.getX()
        self.player.setX(cur + (target_x - cur) * min(1.0, dt * 14.0))

        if not self.game_over:
            # forward movement
            self.player_y += self.speed * dt
            self.player.setY(self.player_y)

            # gravity
            if not self.on_ground:
                self.vz -= 20.0 * dt
                self.player_z += self.vz * dt
                if self.player_z <= 1.0:
                    self.player_z = 1.0
                    self.vz = 0.0
                    self.on_ground = True
            self.player.setZ(self.player_z)

            # move ground tiles to simulate running
            for tile in self.ground_tiles:
                # keep under camera/player: tiles reposition ahead when behind
                while tile.getY() + 14 < self.player_y - 10:
                    tile.setY(tile.getY() + 14 * len(self.ground_tiles))

            for m in self.lane_markers:
                while m.getY() + 10 < self.player_y - 10:
                    m.setY(m.getY() + 10 * 8)

            # update shadow
            self.shadow.setPos(self.player.getX(), self.player.getY(), 0.02)
            s = 0.7 if self.on_ground else max(0.35, 0.7 - (self.player_z - 1.0) * 0.08)
            self.shadow.setScale(s, s, 1)

            # obstacles: move relative by respawning ahead when behind
            for ob in self.obstacles:
                if ob.getY() < self.player_y - 8:
                    ob.setY(self.player_y + 120 + random.random() * 60)
                    ob.setX(LANES[random.randint(0, 2)])

            # collisions
            for ob in self.obstacles:
                if self._collides(ob):
                    # If obstacle is low and player isn't jumping high enough => crash
                    req_jump = ob.getPythonTag("requires_jump")
                    if req_jump and self.on_ground:
                        self._set_game_over()
                        break
                    # if high obstacle, must stay low (we don't have slide), so always crash
                    if not req_jump:
                        self._set_game_over()
                        break

            # score & difficulty
            self.score += int(self.speed * dt * 2)
            t = time.time() - self.time_start
            self.speed = 18.0 + (t / 10.0) * self.speed_increase
            self.score_text.setText(f"Score: {self.score}")

        # camera follows
        self.camera.setY(self.player_y - 16)

        return Task.cont

    def _set_game_over(self):
        self.game_over = True
        self.gameover_text.setText("GAME OVER\nAppuie sur R")


def main():
    app = RunnerGame()
    app.run()


if __name__ == "__main__":
    main()
