# -*- coding: utf-8 -*-
"""纯 Python 2D 弹球物理引擎(无第三方依赖, 可无头测试)。

球台平面 x 向右、y 向上(指向台顶)。所有几何体返回的事件以元组列表形式
由 World.advance() 返回, 由上层规则模块(rules.py)消费。
"""
import math
from . import config as C


class Vec2:
    __slots__ = ("x", "y")

    def __init__(self, x=0.0, y=0.0):
        self.x = float(x)
        self.y = float(y)

    def __add__(self, o):  return Vec2(self.x + o.x, self.y + o.y)
    def __sub__(self, o):  return Vec2(self.x - o.x, self.y - o.y)
    def __mul__(self, k):  return Vec2(self.x * k, self.y * k)
    __rmul__ = __mul__
    def dot(self, o):      return self.x * o.x + self.y * o.y
    def length(self):      return math.hypot(self.x, self.y)
    def norm(self):
        l = self.length()
        return Vec2(self.x / l, self.y / l) if l > 1e-12 else Vec2(0, 0)
    def perp(self):        return Vec2(-self.y, self.x)   # 逆时针旋转 90°
    def copy(self):        return Vec2(self.x, self.y)
    def __repr__(self):    return "Vec2(%.3f,%.3f)" % (self.x, self.y)


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


class Ball:
    _next_id = 0

    def __init__(self, pos, vel=(0, 0), r=C.BALL_R):
        Ball._next_id += 1
        self.id = Ball._next_id
        self.pos = Vec2(*pos)
        self.vel = Vec2(*vel)
        self.r = r
        self.held = False        # 被发射杆/虫洞等扣住
        self.still_time = 0.0    # 防卡死计时

    def speed(self):
        return self.vel.length()


# ---------------------------------------------------------------- 碰撞体
class Shape:
    """基类: 所有碰撞体实现 collide(ball, now) -> None, 事件由子类追加。"""
    kind = "shape"

    def __init__(self, name=""):
        self.name = name


def _resolve_segment(ball, p1, p2, e, mu):
    """圆 vs 线段: 返回 (命中, 法线, 法向接近速度)。命中时已完成位置与速度修正。"""
    d = p2 - p1
    dd = d.dot(d)
    if dd < 1e-12:
        return False, None, 0.0
    t = clamp((ball.pos - p1).dot(d) / dd, 0.0, 1.0)
    q = p1 + d * t
    dist = ball.pos - q
    L = dist.length()
    if L >= ball.r or L < 1e-9:
        return False, None, 0.0
    n = dist * (1.0 / L)                 # 指向球
    ball.pos = q + n * ball.r            # 推出穿透
    vn = ball.vel.dot(n)
    if vn < -0.08:                       # 有明显接近速度才反弹
        # 法向按恢复系数反弹, 切向按摩擦衰减
        vn_after = -vn * e
        vt = ball.vel - n * vn
        ball.vel = n * vn_after + vt * (1.0 - mu)
        return True, n, vn
    return True, n, vn                   # 静止接触: 仅推出位置


class Wall(Shape):
    kind = "wall"

    def __init__(self, p1, p2, name="", e=C.WALL_E, mu=C.WALL_MU):
        super().__init__(name)
        self.p1 = Vec2(*p1)
        self.p2 = Vec2(*p2)
        self.e, self.mu = e, mu

    def collide(self, ball, now):
        _resolve_segment(ball, self.p1, self.p2, self.e, self.mu)


class OneWayGate(Wall):
    """单向门: 球速在 pass_dir 方向分量 > 0 时不碰撞(允许穿过), 否则视为实体墙。"""
    def __init__(self, p1, p2, pass_dir, name="gate"):
        super().__init__(p1, p2, name)
        self.pass_dir = Vec2(*pass_dir).norm()

    def collide(self, ball, now):
        if ball.vel.dot(self.pass_dir) > 0.05:
            return
        _resolve_segment(ball, self.p1, self.p2, self.e, self.mu)


class Post(Shape):
    kind = "post"

    def __init__(self, center, r, name="", e=C.POST_E, active=True):
        super().__init__(name)
        self.c = Vec2(*center)
        self.r = r
        self.e = e
        self.active = active

    def collide(self, ball, now):
        if not self.active:
            return
        dist = ball.pos - self.c
        L = dist.length()
        if L >= self.r + ball.r or L < 1e-9:
            return
        n = dist * (1.0 / L)
        ball.pos = self.c + n * (self.r + ball.r)
        vn = ball.vel.dot(n)
        if vn < -0.08:
            vn_after = -vn * self.e
            vt = ball.vel - n * vn
            ball.vel = n * vn_after + vt * (1.0 - C.WALL_MU)


class Bumper(Post):
    """攻击缓冲器: 撞击后沿法线弹出固定速度。"""
    kind = "bumper"

    def __init__(self, center, r=0.031, name="bumper", kick=C.BUMPER_KICK):
        super().__init__(center, r, name)
        self.kick = kick
        self.last_fire = -1.0

    def collide(self, ball, now):
        dist = ball.pos - self.c
        L = dist.length()
        if L >= self.r + ball.r or L < 1e-9:
            return
        n = dist * (1.0 / L)
        ball.pos = self.c + n * (self.r + ball.r)
        speed = max(self.kick, ball.speed() * 0.9)
        ball.vel = n * speed
        if now - self.last_fire > 0.10:
            self.last_fire = now
            self.fire_event = ("bumper", self.name)
        else:
            self.fire_event = None


class Slingshot(Wall):
    """三角弹弓: 足够速度撞上迎面时主动弹射。"""
    kind = "sling"

    def __init__(self, p1, p2, name="sling", kick=C.SLING_KICK):
        super().__init__(p1, p2, name, e=0.3)
        self.kick = kick
        self.last_fire = -1.0

    def collide(self, ball, now):
        hit, n, vn = _resolve_segment(ball, self.p1, self.p2, self.e, self.mu)
        if hit and vn < -0.35 and now - self.last_fire > 0.18:
            self.last_fire = now
            ball.vel = n * self.kick + ball.vel * 0.15
            self.fire_event = ("sling", self.name)
        else:
            self.fire_event = None


class DropTarget(Wall):
    """奖章降落靶: 被击中即倒下(active=False), 不再参与碰撞。"""
    kind = "drop_target"

    def __init__(self, p1, p2, name="medal", idx=0):
        super().__init__(p1, p2, name, e=0.45)
        self.idx = idx
        self.active = True

    def collide(self, ball, now):
        if not self.active:
            return
        hit, n, vn = _resolve_segment(ball, self.p1, self.p2, self.e, self.mu)
        if hit and vn < -0.15:
            self.active = False
            self.fire_event = ("medal_target", self.idx)
        else:
            self.fire_event = None


class StandupTarget(Wall):
    """站立任务靶: 不倒下, 冷却触发事件。"""
    kind = "mission_target"

    def __init__(self, p1, p2, name="mission", idx=0):
        super().__init__(p1, p2, name, e=0.35)
        self.idx = idx
        self.last_fire = -1.0

    def collide(self, ball, now):
        hit, n, vn = _resolve_segment(ball, self.p1, self.p2, self.e, self.mu)
        if hit and vn < -0.15 and now - self.last_fire > 0.30:
            self.last_fire = now
            self.fire_event = ("mission_target", self.idx)
        else:
            self.fire_event = None


class Flipper:
    """弹板: 绕枢轴旋转的变径胶囊(根部粗尖端细)。

    angle 为摆臂方向角(弧度)。左板静止角约 -0.55, 上摆到 +0.52;
    右板镜像: 静止 pi+0.55, 上摆 pi-0.52。
    """
    def __init__(self, pivot, rest_angle, active_angle, name="flipper",
                 length=C.FLIPPER_LEN, r0=C.FLIPPER_R0, r1=C.FLIPPER_R1):
        self.pivot = Vec2(*pivot)
        self.rest = rest_angle
        self.active = active_angle
        self.angle = rest_angle
        self.ang_vel = 0.0
        self.engaged = False
        self.force_down = False      # TILT 时强制放下
        self.length = length
        self.r0, self.r1 = r0, r1
        self.name = name

    def update(self, dt):
        if self.force_down:
            self.engaged = False
        target = self.active if self.engaged else self.rest
        diff = target - self.angle
        w = C.FLIPPER_W_UP if (target > self.angle) else C.FLIPPER_W_DOWN
        step = w * dt
        if abs(diff) <= step:
            self.angle, self.ang_vel = target, 0.0
        else:
            self.angle += math.copysign(step, diff)
            self.ang_vel = math.copysign(w, diff)

    def collide(self, ball, now):
        d = Vec2(math.cos(self.angle), math.sin(self.angle))
        a = self.pivot
        b = a + d * self.length
        axis = b - a
        t = clamp((ball.pos - a).dot(axis) / axis.dot(axis), 0.0, 1.0)
        q = a + axis * t
        r = self.r0 + (self.r1 - self.r0) * t
        dist = ball.pos - q
        L = dist.length()
        if L >= r + ball.r or L < 1e-9:
            return
        n = dist * (1.0 / L)
        ball.pos = q + n * (r + ball.r)
        # 接触点表面速度 = ω × r
        v_surf = self.perp_from(q) * self.ang_vel
        v_rel = ball.vel - v_surf
        vn = v_rel.dot(n)
        if vn < 0.0:
            ball.vel = ball.vel - n * ((1.0 + C.FLIPPER_E) * vn)
            sp = ball.speed()
            if sp > C.VMAX:
                ball.vel = ball.vel * (C.VMAX / sp)

    def perp_from(self, q):
        v = q - self.pivot
        return Vec2(-v.y, v.x)


class Zone:
    """非碰撞触发区(滚灯/收纳井/发射杆区)。"""
    kind = "zone"

    def check(self, ball, now):
        return None


class Rollover(Zone):
    """滚过触发区: 球心进入圆形区域触发一次, 离开后重置; 可选方向过滤。"""
    def __init__(self, center, r, name, require_dir=None):
        self.c = Vec2(*center)
        self.r = r
        self.name = name
        self.require_dir = Vec2(*require_dir) if require_dir else None
        self.inside = False

    def check(self, ball, now):
        d2 = (ball.pos.x - self.c.x) ** 2 + (ball.pos.y - self.c.y) ** 2
        ins = d2 <= self.r * self.r
        evt = None
        if ins and not self.inside:
            if self.require_dir is None or ball.vel.dot(self.require_dir) > 0.3:
                evt = ("rollover", self.name)
        self.inside = ins
        return evt


class Saucer(Zone):
    """收纳井(虫洞/超空间/出球道救援): 慢速进入的球被扣住, 延迟后从指定点弹出。

    armed_fn(name)->bool 由上层注入, 决定该井当前是否激活(如出球道救援灯)。
    """
    def __init__(self, center, r, name, eject_vel, eject_pos=None,
                 capture_speed=1.5, delay=0.8):
        self.c = Vec2(*center)
        self.r = r
        self.name = name
        self.eject_vel = Vec2(*eject_vel)
        self.eject_pos = Vec2(*eject_pos) if eject_pos else self.c
        self.capture_speed = capture_speed
        self.delay = delay
        self.holding = None
        self.timer = 0.0
        self.cool = -1.0

    def update(self, dt, events):
        if self.holding is not None:
            self.timer -= dt
            if self.timer <= 0:
                b = self.holding
                self.holding = None
                b.held = False
                b.pos = self.eject_pos.copy()
                b.vel = self.eject_vel.copy()
                self.cool = 1.0
                events.append(("saucer_out", self.name))

    def check(self, ball, now):
        if self.holding is not None or now < self.cool:
            return None
        d2 = (ball.pos.x - self.c.x) ** 2 + (ball.pos.y - self.c.y) ** 2
        if d2 <= self.r * self.r and ball.speed() < self.capture_speed:
            self.holding = ball
            ball.held = True
            ball.vel = Vec2(0, 0)
            self.timer = self.delay
            return ("saucer", self.name)
        return None


class PlungerZone(Zone):
    """发射杆区: 球低速停留在此区域时上报, 由上层锁球并接管蓄力。"""
    def __init__(self, x0, x1, y0, y1, name="plunger"):
        self.box = (x0, x1, y0, y1)
        self.name = name
        self.fired = False

    def check(self, ball, now):
        x0, x1, y0, y1 = self.box
        ins = x0 <= ball.pos.x <= x1 and y0 <= ball.pos.y <= y1
        evt = None
        # 球可能快速穿过本区(inside 已置位), 必须在"停在区内"时也能触发
        if ins and ball.speed() < 0.25 and not self.fired:
            self.fired = True
            evt = ("plunger", ball)
        if not ins:
            self.fired = False
        return evt


# ---------------------------------------------------------------- 世界
class World:
    def __init__(self):
        self.walls = []          # Wall/OneWayGate/Slingshot/DropTarget/StandupTarget
        self.posts = []          # Post/Bumper
        self.flippers = []
        self.zones = []          # Rollover/Saucer/PlungerZone
        self.balls = []
        self.time = 0.0
        self.armed_fn = None     # callable(name)->bool, 收纳井是否激活
        self.events = []         # 单帧事件缓存
        Ball._next_id = 0

    # —— 构建辅助 ——
    def add(self, *shapes):
        for s in shapes:
            if isinstance(s, Flipper):
                self.flippers.append(s)
            elif isinstance(s, Zone):
                self.zones.append(s)
            elif isinstance(s, Post):
                self.posts.append(s)
            else:
                self.walls.append(s)
        return shapes[0] if len(shapes) == 1 else shapes

    def add_ball(self, pos, vel=(0, 0)):
        b = Ball(pos, vel)
        self.balls.append(b)
        return b

    def remove_ball(self, b):
        if b in self.balls:
            self.balls.remove(b)
        for z in self.zones:
            if isinstance(z, Saucer) and z.holding is b:
                z.holding = None
            elif isinstance(z, PlungerZone):
                z.fired = False

    def clear_balls(self):
        for b in list(self.balls):
            self.remove_ball(b)

    def nudge(self, impulse):
        """推台: 给所有自由球一个冲量。"""
        for b in self.balls:
            if not b.held:
                b.vel = b.vel + Vec2(*impulse)

    # —— 主步进 ——
    def advance(self, dt):
        self.events = []
        steps = max(1, int(math.ceil(dt / C.SUB_DT)))
        sub = dt / steps
        for _ in range(steps):
            self.time += sub
            self._step(sub)
        return self.events

    def _step(self, dt):
        ev = self.events
        for f in self.flippers:
            f.update(dt)
        for z in self.zones:
            if isinstance(z, Saucer):
                z.update(dt, ev)

        for b in self.balls:
            if b.held:
                continue
            b.vel.y -= C.G * dt
            b.vel *= (1.0 - C.AIR_DRAG * dt)
            sp = b.speed()
            if sp > C.VMAX:
                b.vel = b.vel * (C.VMAX / sp)
            b.pos = b.pos + b.vel * dt
            # 防卡死: 长时间低速静止时轻微扰动
            if sp < 0.02:
                b.still_time += dt
                if b.still_time > 12.0:
                    b.vel = Vec2(0.15 * math.sin(self.time * 3.0), 0.25)
                    b.still_time = 0.0
            else:
                b.still_time = 0.0

        # 两轮碰撞求解, 提高堆叠稳定性
        for _ in range(2):
            for b in self.balls:
                if b.held:
                    continue
                for w in self.walls:
                    w.collide(b, self.time)
                    if getattr(w, "fire_event", None):
                        ev.append(w.fire_event)
                        w.fire_event = None
                for p in self.posts:
                    p.collide(b, self.time)
                    if getattr(p, "fire_event", None):
                        ev.append(p.fire_event)
                        p.fire_event = None
                for f in self.flippers:
                    f.collide(b, self.time)
            self._ball_ball()

        # 落沟与触发区
        for b in list(self.balls):
            if b.held:
                continue
            if b.pos.y < C.DRAIN_Y:
                ev.append(("drain", b))
                self.remove_ball(b)
                continue
            for z in self.zones:
                if isinstance(z, Saucer):
                    # 出球道救援井仅在点亮时才收纳, 其余井始终激活
                    armed = (not z.name.startswith("outlane")
                             or self.armed_fn is None
                             or self.armed_fn(z.name))
                    if armed:
                        e = z.check(b, self.time)
                        if e:
                            ev.append(e)
                else:
                    e = z.check(b, self.time)
                    if e:
                        ev.append(e)

    def _ball_ball(self):
        n = len(self.balls)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = self.balls[i], self.balls[j]
                if a.held or b.held:
                    continue
                d = b.pos - a.pos
                L = d.length()
                if L >= a.r + b.r or L < 1e-9:
                    continue
                nrm = d * (1.0 / L)
                overlap = a.r + b.r - L
                a.pos = a.pos - nrm * (overlap * 0.5)
                b.pos = b.pos + nrm * (overlap * 0.5)
                vrel = (a.vel - b.vel).dot(nrm)
                if vrel > 0:
                    imp = nrm * (vrel * 0.95)
                    a.vel = a.vel - imp
                    b.vel = b.vel + imp
