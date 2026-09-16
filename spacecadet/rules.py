# -*- coding: utf-8 -*-
"""游戏规则状态机: 计分、任务、军衔晋升、多球、燃料、倾台(TILT)。

设计参照原作机制并做了简化:
- 军衔靠完成任务晋升(共 9 阶), 晋升送加分与一个备用球;
- 任务由击中任务靶开启, 有燃料(倒计时)限制, 绿色虫洞可补燃料;
- 奖章靶组点亮奖章灯(蓝→红→紫), 紫灯时集齐一组 = 救球;
- 超空间滑道 5 级奖励灯, 第 3 级升起中央立柱, 第 4 级点亮出球道救援,
  第 5 级触发多球后清零重积;
- 多球期间任务进度冻结(沿用原版规则);
- 连续推台会触发 TILT, 弹板失效直至丢球。
"""
import random
from collections import deque
from . import config as C

RANKS = [
    ("军校生",   "Cadet"),
    ("少尉",     "Ensign"),
    ("中尉",     "Lieutenant"),
    ("上尉",     "Captain"),
    ("少校",     "Major"),
    ("中校",     "Commander"),
    ("上校",     "Commodore"),
    ("准将",     "Admiral"),
    ("舰队上将", "Fleet Admiral"),
]
# 晋升到下一阶所需完成的任务数(索引 = 当前阶)
MISSIONS_NEEDED = [2, 3, 3, 3, 3, 4, 4, 5]

# tier: 0=军校生即可接, 1=少尉/中尉, 2=上尉及以上
MISSIONS = [
    dict(id="launch",  tier=0, name="发射训练",   obj="由左侧发射坡道上行 3 次",        prog=3,  reward=125000, event="launch_ramp"),
    dict(id="reentry", tier=0, name="再入训练",   obj="通过再入航道滚灯 3 次",          prog=3,  reward=125000, event="reentry"),
    dict(id="attack",  tier=0, name="攻击训练",   obj="撞击攻击缓冲器 15 次",           prog=15, reward=125000, event="bumper"),
    dict(id="science", tier=0, name="科学考察",   obj="击落整组奖章降落靶 3 组",        prog=3,  reward=200000, event="medal_bank"),
    dict(id="rescue",  tier=1, name="营救行动",   obj="依次进入黄色、绿色虫洞",         prog=2,  reward=350000, event="rescue_seq"),
    dict(id="recon",   tier=1, name="侦察任务",   obj="击中任务靶 3 次",                prog=3,  reward=300000, event="mission_target"),
    dict(id="hyper",   tier=2, name="超空间跃迁", obj="进入超空间滑道 3 次",            prog=3,  reward=500000, event="hyperspace"),
    dict(id="worm",    tier=2, name="虫洞穿梭",   obj="进入任意虫洞 3 次",              prog=3,  reward=500000, event="wormhole"),
]

MEDAL_STAGES = ["蓝", "红", "紫"]


class Game:
    def __init__(self, on_event=None):
        self.on_event = on_event      # 回调(notify, payload), 渲染层用来播动画
        self.hiscore = 0              # 跨局保留
        self.reset()

    # ------------------------------------------------ 基础
    def reset(self):
        self.score = 0
        self.state = "ready"          # ready / play / gameover
        self.ball_num = 1             # 当前球号(1 起)
        self.total_balls = C.BALLS_PER_GAME
        self.balls_in_play = 0
        self.rank = 0
        self.rank_done = 0            # 本阶已完成任务数
        self.completed = set()        # 已完成任务 id
        self.mission = None           # 进行中的任务 dict + progress/fuel
        self.mission_progress = 0
        self.fuel = 0.0
        self.hyper_lights = 0         # 超空间灯 0~5
        self.medal_stage = 0          # 奖章灯 0~3 (蓝/红/紫)
        self.medal_banks = 0          # 本球击落组数(定倍率)
        self.multiplier = 1
        self.kicker_lit = False       # 出球道救援
        self.center_post = False
        self.gravity_time = 0.0       # 重力加倍剩余
        self.tilt_heat = 0.0
        self.tilted = False
        self.multiball_freeze_notified = False
        self.plunger_ball = None      # 被发射杆扣住的球
        self.toasts = deque()         # (主文本, 副文本, 颜色)
        self.spawn_requests = []      # 请求渲染/世界层生成球(多球)
        self.stats = dict(bumpers=0, ramps=0)

    def notify(self, text, sub="", color="info"):
        self.toasts.append((text, sub, color))
        if self.on_event:
            self.on_event("toast", (text, sub, color))

    # ------------------------------------------------ 分数
    def add_score(self, base):
        v = base * self.multiplier
        if self.gravity_time > 0:
            v *= 2
        self.score += int(v)
        return int(v)

    def rank_name(self):
        return RANKS[self.rank]

    # ------------------------------------------------ 任务
    def unlocked_missions(self):
        tier_max = 0 if self.rank == 0 else (1 if self.rank <= 2 else 2)
        return [m for m in MISSIONS if m["tier"] <= tier_max]

    def start_mission(self):
        pool = [m for m in self.unlocked_missions() if m["id"] not in self.completed]
        if not pool:
            pool = self.unlocked_missions()
        m = random.choice(pool)
        self.mission = m
        self.mission_progress = 0
        self.fuel = 50.0
        self.notify("任务开始: %s" % m["name"], m["obj"], "mission")

    def abort_mission(self, reason=""):
        if self.mission:
            self.notify("任务中止 %s" % reason, self.mission["name"], "warn")
            self.mission = None
            self.fuel = 0.0

    def _mission_progress(self, event, extra=None):
        m = self.mission
        if m is None or self.balls_in_play > 1:   # 多球冻结
            if m is not None and self.balls_in_play > 1 and not self.multiball_freeze_notified:
                self.multiball_freeze_notified = True
                self.notify("多球进行中", "任务进度暂停", "warn")
            return
        # 营救行动要求顺序: 先黄后绿
        if m["event"] == "rescue_seq":
            want = "yellow" if self.mission_progress == 0 else "green"
            if extra == want:
                self.mission_progress += 1
            return
        if m["event"] == event:
            self.mission_progress += 1
            if self.mission_progress >= m["prog"]:
                self.complete_mission()

    def complete_mission(self):
        m = self.mission
        self.score += m["reward"]
        self.completed.add(m["id"])
        self.mission = None
        self.fuel = 0.0
        self.rank_done += 1
        self.notify("任务完成: %s" % m["name"], "+%s" % fmt(m["reward"]), "good")
        need = MISSIONS_NEEDED[self.rank] if self.rank < len(MISSIONS_NEEDED) else 0
        if self.rank >= len(RANKS) - 1:
            return
        if self.rank_done >= need:
            self.rank += 1
            self.rank_done = 0
            bonus = self.rank * 250000
            self.score += bonus
            self.total_balls += 1
            self.notify("晋升 %s!" % RANKS[self.rank][0],
                        "奖励 %s + 备用球" % fmt(bonus), "rank")

    # ------------------------------------------------ 事件入口
    def handle(self, evt, meta):
        kind = evt[0]
        if kind == "drain":
            self._on_drain(evt[1])
        elif kind == "plunger":
            b = evt[1]
            self.plunger_ball = b
            b.held = True
            b.pos.x, b.pos.y = 0.574, 0.054   # 吸附到发射杆停靠位(避免悬停半空)
            b.vel.x = b.vel.y = 0.0
            if self.state == "play" and self.balls_in_play <= 1:
                # 弱发射未出通道、球回落发射杆: 回到待发射状态,
                # 否则蓄力逻辑(state==ready)永不生效, 游戏死锁
                self.state = "ready"
        elif kind == "bumper":
            self.add_score(C.SCORE_BUMPER)
            self.stats["bumpers"] += 1
            self._mission_progress("bumper")
            self._on_event("bumper", evt[1])
        elif kind == "sling":
            self.add_score(C.SCORE_SLING)
        elif kind == "rollover":
            self._on_rollover(evt[1])
        elif kind == "medal_target":
            self.add_score(C.SCORE_MEDAL_TARGET)
            if all(not t.active for t in meta.medals):
                self._on_medal_bank()
        elif kind == "mission_target":
            self.add_score(C.SCORE_MISSION_TARGET)
            if self.mission is None and not self.tilted:
                self.start_mission()
            else:
                self._mission_progress("mission_target")
        elif kind == "saucer":
            self._on_saucer(evt[1])
        elif kind == "saucer_out":
            self._on_event("saucer_out", evt[1])

    def _on_rollover(self, name):
        if name == "launch_ramp":
            self.add_score(C.SCORE_LAUNCH_RAMP)
            self.stats["ramps"] += 1
            self._mission_progress("launch_ramp")
            self._on_event("flash", "launch_ramp")
        elif name in ("reentry_l", "reentry_r"):
            self.add_score(C.SCORE_REENTRY)
            self._mission_progress("reentry")
            self._on_event("flash", name)

    def _on_medal_bank(self):
        self.add_score(C.SCORE_MEDAL_BANK)
        self.medal_banks += 1
        idx = min(self.medal_banks - 1, len(C.MULTIPLIER_LADDER) - 1)
        self.multiplier = C.MULTIPLIER_LADDER[idx]
        self._mission_progress("medal_bank")
        self._on_event("medal_bank", None)
        if self.medal_stage >= 3:
            self.medal_stage = 0
            self.total_balls += 1
            self.notify("奖章紫灯达成!", "救球 +1", "good")
        else:
            self.medal_stage += 1
            self.notify("奖章灯点亮: %s" % MEDAL_STAGES[self.medal_stage - 1],
                        "倍率 ×%d" % self.multiplier, "info")

    def _on_saucer(self, name):
        if name == "hyperspace":
            self._hyper_step()
            self._mission_progress("hyperspace")
        elif name == "yellow":
            self._mission_progress("rescue_seq", "yellow")
            self._mission_progress("wormhole")
            if self.medal_stage >= 3:
                self.medal_stage = 1
                self.total_balls += 1
                self.notify("虫洞救球!", "备用球 +1", "good")
            else:
                self.add_score(C.SCORE_YELLOW_WORMHOLE)
                self.notify("黄色虫洞", "+%s" % fmt(C.SCORE_YELLOW_WORMHOLE), "info")
        elif name == "green":
            self._mission_progress("rescue_seq", "green")
            self._mission_progress("wormhole")
            if self.mission:
                self.fuel = min(60.0, self.fuel + 20.0)
                self.notify("燃料补充 +20s", "任务时限延长", "info")
            else:
                self.notify("绿色虫洞", "+%s" % fmt(C.SCORE_GREEN_WORMHOLE), "info")
                self.add_score(C.SCORE_GREEN_WORMHOLE)
        elif name.startswith("outlane"):
            self.kicker_lit = False
            self.notify("出球道救援!", "球被弹回", "good")
            self._on_event("flash", name)

    def _hyper_step(self):
        self.hyper_lights += 1
        pts, note = C.HYPERSPACE_AWARDS[self.hyper_lights - 1]
        if self.hyper_lights == 3:
            self.center_post = True
            self._on_event("center_post", True)
        elif self.hyper_lights == 4:
            self.kicker_lit = True
        elif self.hyper_lights == 5:
            self.spawn_requests.append("multiball")
            self.hyper_lights = 0
            self.center_post = False
            self._on_event("center_post", False)
            self.notify("第 5 级: 多球!", note, "rank")
        self.add_score(pts)
        self.notify("超空间 Lv.%d" % self.hyper_lights if self.hyper_lights else "超空间奖励",
                    "+%s %s" % (fmt(pts), note), "info")

    # ------------------------------------------------ 丢球 / 多球 / 推台
    def _on_drain(self, ball):
        self.balls_in_play = max(0, self.balls_in_play - 1)
        if self.balls_in_play > 0:
            return
        # 本球结束
        self.tilted = False
        self.multiball_freeze_notified = False
        self.abort_mission("(丢球)")
        self.multiplier = 1
        self.medal_banks = 0
        self.kicker_lit = False
        self.center_post = False
        self.gravity_time = 0.0
        self._on_event("center_post", False)
        if self.ball_num < self.total_balls:
            self.ball_num += 1
            self.state = "ready"
            self.notify("第 %d 球" % self.ball_num, "备用球 %d" % (self.total_balls - self.ball_num), "info")
        else:
            self.state = "gameover"
            # 结束画面由渲染层的 overlay 全屏负责; 不再额外弹 toast,
            # 否则会出现两个"游戏结束"且文字互相重叠
            self._on_event("gameover", None)

    def spawn_multiball(self):
        self.balls_in_play += 2
        self.notify("多球!", "场上 %d 球" % self.balls_in_play, "rank")

    def nudge(self, direction):
        if self.tilted or self.state != "play":
            return False
        self.tilt_heat += 1.0
        if self.tilt_heat > 2.5:
            self.tilted = True
            self.abort_mission("(倾台)")
            self.notify("TILT!", "弹板失效直至丢球", "warn")
            self._on_event("tilt", None)
            return True
        return False

    # ------------------------------------------------ 帧更新
    def tick(self, dt):
        self.tilt_heat = max(0.0, self.tilt_heat - dt * 0.35)
        if self.gravity_time > 0:
            self.gravity_time = max(0.0, self.gravity_time - dt)
        if self.mission and self.balls_in_play == 1 and self.state == "play":
            self.fuel -= dt
            if self.fuel <= 0:
                self.abort_mission("(燃料耗尽)")

    def launch(self):
        """发射杆释放: 解锁球并切入 play 状态, 返回球对象(速度由调用方设置)。"""
        b = self.plunger_ball
        if b is None:
            return None
        self.plunger_ball = None
        b.held = False
        self.state = "play"
        self.balls_in_play = 1
        return b

    def _on_event(self, name, payload):
        if self.on_event:
            self.on_event(name, payload)


def fmt(n):
    return "{:,}".format(n)
