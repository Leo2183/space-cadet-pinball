# -*- coding: utf-8 -*-
"""无头物理/规则自动化测试: python tests/test_physics.py"""
import os
import sys
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from spacecadet import table as T
from spacecadet import physics as P
from spacecadet import rules as R
from spacecadet import config as C


def run_world(meta, seconds, collect=True):
    """以 60fps 步进世界, 返回事件流。"""
    events = []
    dt, n = 1.0 / 60.0, int(seconds * 60)
    for _ in range(n):
        evs = meta.world.advance(dt)
        if collect:
            events.extend(evs)
    return events


def count(events, kind):
    return sum(1 for e in events if e[0] == kind)


# ---------------------------------------------------------------- 用例
def test_ball_settles_on_floor():
    m = T.build_table()
    m.world.add_ball((0.30, 0.40))
    run_world(m, 2.0, collect=False)
    b = m.world.balls[0]
    assert 0.0 < b.pos.x < 0.60, "球应留在台内, 实际 %s" % b.pos
    assert b.pos.y < 0.12 or b.speed() < 0.5, "球应落到下半场, %s v=%s" % (b.pos, b.vel)


def test_plunger_full_launch_reaches_playfield():
    m = T.build_table()
    b = m.world.add_ball((0.574, 0.30))
    # 等球落到发射杆
    run_world(m, 1.5, collect=False)
    assert b.pos.y < 0.12 and b.pos.x > 0.548, "球应停在发射杆上: %s" % b.pos
    b.held = False
    b.vel = P.Vec2(0, C.PLUNGER_VMAX)
    evs = run_world(m, 3.0)
    assert b.pos.x < 0.548 or b.pos.y > 0.5, "满力发射应越过单向门进入台面: %s" % b.pos
    assert any(e[0] == "drain" for e in evs) or b in m.world.balls


def test_plunger_zone_event():
    """球从高处落入发射杆区并停稳后, 必须触发 plunger 事件(回归: 快速穿过不再卡死)。"""
    m = T.build_table()
    m.world.add_ball(T.spawn_position())
    evs = run_world(m, 3.0)
    assert any(e[0] == "plunger" for e in evs), "球停稳后应触发发射杆事件"


def test_no_stuck_top_left():
    """回归: 从顶部弧线回落的球必须能落回左侧轨道, 不卡在导板死角。"""
    m = T.build_table()
    b = m.world.add_ball((0.035, 1.05), (0.25, -1.2))
    reached_lower = False
    for _ in range(int(4.0 * 60)):
        m.world.advance(1.0 / 60.0)
        if b in m.world.balls and b.pos.y < 0.75:
            reached_lower = True
            break
        if b not in m.world.balls:
            reached_lower = True   # 已落沟也说明没有卡死
            break
    assert reached_lower, "球卡在左上角: %s v=%.2f" % (b.pos, b.speed())


def test_gate_blocks_reentry():
    m = T.build_table()
    # 从台面上方向下压向航道口, 应被单向门弹回台面而非落入航道
    b = m.world.add_ball((0.574, 1.05), (0.0, -1.5))
    run_world(m, 2.0, collect=False)
    assert not (b.pos.x > 0.548 and b.pos.y < 0.95 and b in m.world.balls), \
        "球不应穿门回落发射航道: %s" % b.pos


def test_flipper_shot_reaches_top():
    m = T.build_table()
    b = m.world.add_ball((0.26, 0.16), (0.0, 0.0))
    run_world(m, 0.6, collect=False)   # 球落到弹板上
    m.flipper_left.engaged = True
    peak = 0.0
    dt = 1.0 / 60.0
    for _ in range(int(3.0 * 60)):
        m.world.advance(dt)
        peak = max(peak, b.pos.y if b in m.world.balls else peak)
        if b not in m.world.balls:
            break
    assert peak > 0.75, "弹板击球应能打到上半场, 峰值 y=%.2f" % peak


def test_flipper_direction():
    # 左弹板上摆必须把球打向右上方
    m = T.build_table()
    b = m.world.add_ball((0.25, 0.16))
    run_world(m, 0.6, collect=False)
    m.flipper_left.engaged = True
    hit_vx = None
    dt = 1.0 / 60.0
    for _ in range(int(1.5 * 60)):
        prev = b.speed()
        m.world.advance(dt)
        if b.speed() > prev + 0.5:
            hit_vx = b.vel.x
            break
    assert hit_vx is not None and hit_vx > 0.5, "左弹板应把球甩向右侧, vx=%s" % hit_vx


def test_bumper_kicks_and_scores():
    m = T.build_table()
    b = m.world.add_ball((0.245, 0.70), (0.0, 2.0))    # 向上撞 0 号缓冲器
    hit_speed, fired = 0.0, False
    for _ in range(int(1.5 * 60)):
        evs = m.world.advance(1.0 / 60.0)
        if any(e[0] == "bumper" for e in evs):
            fired = True
            hit_speed = max(hit_speed, b.speed())
    assert fired, "撞击缓冲器应触发事件"
    assert hit_speed >= C.BUMPER_KICK * 0.8, "缓冲器应以固定弹速出球: %.2f" % hit_speed


def test_medal_targets_drop_and_reset():
    m = T.build_table()
    b = m.world.add_ball((0.152, 0.55), (0.0, 1.2))    # 从下方撞 0 号靶
    evs = run_world(m, 0.8)
    assert count(evs, "medal_target") >= 1
    assert not m.medals[0].active, "被击中的降落靶应倒下"
    T.reset_medals(m)
    assert all(t.active for t in m.medals)


def test_saucer_capture_and_eject():
    m = T.build_table()
    b = m.world.add_ball((0.160, 1.00), (0.0, -0.3))   # 慢速落入黄色虫洞
    evs = run_world(m, 2.5)
    assert any(e == ("saucer", "yellow") for e in evs), "应被黄色虫洞收纳"
    assert any(e == ("saucer_out", "yellow") for e in evs), "延迟后应被弹出"


def test_outlane_saucer_only_when_armed():
    m = T.build_table()
    # 未点亮: 球应直接落沟
    m.world.add_ball((0.030, 0.30), (0.0, -0.5))
    evs = run_world(m, 2.0)
    assert any(e[0] == "drain" for e in evs), "未点亮时出球道应落沟"
    # 点亮: 收纳并弹回内道
    m2 = T.build_table()
    m2.world.armed_fn = lambda name: True
    m2.world.add_ball((0.030, 0.30), (0.0, -0.5))
    evs2 = run_world(m2, 2.0)
    assert any(e == ("saucer", "outlane_l") for e in evs2), "点亮时出球道应救援"
    assert any(e == ("saucer_out", "outlane_l") for e in evs2)


def test_ball_ball_collision():
    m = T.build_table()
    a = m.world.add_ball((0.30, 0.50), (0.5, 0.0))
    b = m.world.add_ball((0.36, 0.50), (-0.3, 0.0))
    run_world(m, 0.5, collect=False)
    assert a.pos.x < b.pos.x, "两球不应互相穿过"


def test_fuzz_no_escape():
    """随机 fuzz: 球永远不允许逃出台面边界。"""
    random.seed(42)
    for trial in range(20):
        m = T.build_table()
        ang = random.uniform(0, 6.283)
        spd = random.uniform(1.0, 4.5)
        m.world.add_ball((random.uniform(0.1, 0.5), random.uniform(0.3, 1.0)),
                         (spd * __import__("math").cos(ang), spd * __import__("math").sin(ang)))
        dt = 1.0 / 60.0
        for _ in range(int(8.0 * 60)):
            m.world.advance(dt)
            for b in m.world.balls:
                if b.held:
                    continue
                assert -0.05 < b.pos.x < 0.65 and -0.05 < b.pos.y < 1.22, \
                    "球逃逸! trial=%d pos=%s" % (trial, b.pos)
        m.world.clear_balls()


def test_rules_mission_and_rank():
    g = R.Game()
    m = T.build_table()
    g.state = "play"
    g.balls_in_play = 1
    # 军校生任务: 发射坡道 x3
    g.mission = R.MISSIONS[0]
    g.mission_progress = 0
    g.fuel = 50
    for _ in range(2):
        g.handle(("rollover", "launch_ramp"), m)
    assert g.mission is not None
    g.handle(("rollover", "launch_ramp"), m)
    assert g.mission is None and g.rank_done == 1
    # 再完成一个任务 → 晋升少尉
    g.start_mission()
    g.mission_progress = g.mission["prog"] - 1
    g._mission_progress(g.mission["event"])
    assert g.rank == 1, "两任务后应晋升少尉"
    assert g.total_balls == C.BALLS_PER_GAME + 1


def test_rules_hyperspace_ladder():
    g = R.Game()
    m = T.build_table()
    g.state = "play"
    g.balls_in_play = 1
    for i in range(3):
        g.handle(("saucer", "hyperspace"), m)
    assert g.center_post, "第 3 级应升起中央立柱"
    g.handle(("saucer", "hyperspace"), m)
    assert g.kicker_lit, "第 4 级应点亮出球道救援"
    g.handle(("saucer", "hyperspace"), m)
    assert g.hyper_lights == 0 and g.spawn_requests == ["multiball"]


def test_rules_tilt():
    g = R.Game()
    g.state = "play"
    g.balls_in_play = 1
    for _ in range(3):
        g.nudge("x")
    assert g.tilted


def test_rules_drain_advances_ball():
    g = R.Game()
    m = T.build_table()
    g.state = "play"
    g.balls_in_play = 1
    b = P.Ball((0.3, 0.1))
    g.handle(("drain", b), m)
    assert g.state == "ready" and g.ball_num == 2
    g.state = "play"
    g.balls_in_play = 1
    g.ball_num = g.total_balls
    g.handle(("drain", b), m)
    assert g.state == "gameover"


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

if __name__ == "__main__":
    failed = 0
    for fn in TESTS:
        try:
            fn()
            print("PASS  %s" % fn.__name__)
        except AssertionError as e:
            failed += 1
            print("FAIL  %s: %s" % (fn.__name__, e))
        except Exception as e:
            failed += 1
            print("ERROR %s: %r" % (fn.__name__, e))
    print("\n%d/%d passed" % (len(TESTS) - failed, len(TESTS)))
    sys.exit(1 if failed else 0)
