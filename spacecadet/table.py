# -*- coding: utf-8 -*-
"""球台几何定义 —— 参照《太空军校生》原版布局的复刻设计。

俯视图(物理坐标, x 向右 0~0.60, y 向上 0~1.15, 玩家位于 y=0 一侧):

    ┌─────────────── 顶部弧形导轨 ───────────────┐
    │ 黄色虫洞   ▲缓冲器群▲          超空间滑道 ╲ │发射
    │╱左│                                   ╲ ╲ │航道
    │  航  ◢奖章降落靶(3)          任务靶(3)  ╲ ╲│(右)
    │  道  ┌绿色虫洞┐                     滑道口 │
    │╲  ╲  ╲_______╱                    ╱      │
    │  ╲  ╲____________________________╱       │
    │ 出球道   弹弓   ◁弹板│中央立柱│弹板▷  出球道│
    └──────┬─────────落沟─────────┬─────────────┘

原版关键要素: 发射坡道(左, 单向通向台顶)、再入航道(两侧内道滚灯)、
攻击缓冲器×3、奖章降落靶×3、任务靶×3、黄色/绿色虫洞(互相传送)、
超空间滑道(5级奖励灯)、中央立柱、出球道救援。
"""
from . import physics as P
from . import config as C

W, H = 0.60, 1.15          # 球台外沿
LANE_X = 0.548             # 发射航道内壁


class TableMeta:
    """球台部件句柄集合, 供规则层与渲染层使用。"""
    pass


def build_table():
    w = P.World()
    m = TableMeta()
    m.world = w

    # ---------- 外墙与顶部弧形导轨 ----------
    arc = [(0.0, 1.035), (0.055, 1.100), (0.130, 1.130), (0.220, 1.148),
           (0.310, 1.150), (0.400, 1.148), (0.485, 1.128), (0.555, 1.093),
           (0.600, 1.030)]
    for a, b in zip(arc, arc[1:]):
        w.add(P.Wall(a, b, name="arc"))
    w.add(P.Wall((0.0, 1.035), (0.0, 0.055), name="wall_left"))      # 左外墙(延至出球道底)
    w.add(P.Wall((0.600, 1.030), (0.600, 0.040), name="wall_right")) # 右外墙
    w.add(P.Wall((LANE_X, 0.995), (LANE_X, 0.040), name="lane_inner"))  # 航道内壁
    w.add(P.Wall((LANE_X, 0.040), (0.600, 0.040), name="lane_floor"))   # 航道底
    # 单向门: 只许球从航道向上穿出
    m.gate = P.OneWayGate((LANE_X, 0.995), (0.598, 1.028), (-0.25, 1.0), name="gate")
    w.add(m.gate)

    # ---------- 左侧发射坡道(轨道) ----------
    w.add(P.Wall((0.075, 0.400), (0.075, 0.955), name="orbit_inner"))
    # 顶部斜导板: 悬在轨道口右上方(不与左墙相接, 避免楔形死角)。
    # 上升的球越过轨道口后撞其底面被导向右侧; 回落的球直接落回轨道口。
    w.add(P.Wall((0.090, 0.998), (0.170, 1.045), name="orbit_deflector"))
    # 黄色虫洞(收纳井): 底板 + 后墙 + 井
    w.add(P.Wall((0.115, 0.952), (0.195, 0.945), name="ypocket_floor"))
    w.add(P.Wall((0.195, 0.945), (0.200, 1.015), name="ypocket_back"))
    m.yellow = P.Saucer((0.160, 0.975), 0.032, "yellow",
                        eject_vel=(0.15, 2.3), eject_pos=(0.350, 0.500),
                        capture_speed=1.5, delay=0.9)
    w.add(m.yellow)
    # 发射坡道滚过触发(仅向上经过时计一次)
    m.ro_launch = P.Rollover((0.040, 0.900), 0.035, "launch_ramp",
                             require_dir=(0, 1))
    w.add(m.ro_launch)

    # ---------- 攻击缓冲器 ×3 ----------
    m.bumpers = [
        P.Bumper((0.245, 0.845), name="bumper0"),
        P.Bumper((0.355, 0.845), name="bumper1"),
        P.Bumper((0.300, 0.735), name="bumper2"),
    ]
    for b in m.bumpers:
        w.add(b)

    # ---------- 奖章降落靶 ×3 + 背墙 ----------
    m.medals = [
        P.DropTarget((0.130, 0.662), (0.174, 0.634), name="medal", idx=0),
        P.DropTarget((0.182, 0.628), (0.226, 0.600), name="medal", idx=1),
        P.DropTarget((0.235, 0.594), (0.278, 0.566), name="medal", idx=2),
    ]
    for t in m.medals:
        w.add(t)
    w.add(P.Wall((0.160, 0.708), (0.309, 0.612), name="medal_back"))

    # ---------- 任务靶 ×3 (面朝左, 左弹板击打) ----------
    m.missions = [
        P.StandupTarget((0.415, 0.460), (0.415, 0.500), name="mission", idx=0),
        P.StandupTarget((0.415, 0.545), (0.415, 0.585), name="mission", idx=1),
        P.StandupTarget((0.415, 0.630), (0.415, 0.675), name="mission", idx=2),
    ]
    for t in m.missions:
        w.add(t)

    # ---------- 绿色虫洞(兼燃料井) ----------
    w.add(P.Wall((0.295, 0.415), (0.335, 0.345), name="gpocket_left"))
    w.add(P.Wall((0.405, 0.345), (0.365, 0.415), name="gpocket_right"))
    m.green = P.Saucer((0.350, 0.380), 0.030, "green",
                       eject_vel=(0.90, -0.45), eject_pos=(0.160, 1.000),
                       capture_speed=1.5, delay=0.9)
    w.add(m.green)

    # ---------- 超空间滑道(右, 挂在航道内壁上) ----------
    w.add(P.Wall((LANE_X, 0.885), (0.502, 0.815), name="hs_upper_lip"))
    w.add(P.Wall((LANE_X, 0.715), (0.502, 0.775), name="hs_lower_lip"))
    m.hyperspace = P.Saucer((0.516, 0.790), 0.032, "hyperspace",
                            eject_vel=(-1.8, -0.4), capture_speed=1.6, delay=0.7)
    w.add(m.hyperspace)

    # ---------- 下半场: 弹弓 / 分流墙 / 出球道 ----------
    # 左: 分流墙(外=出球道, 内=再入航道) + 出球道斜底 + 弹弓
    w.add(P.Wall((0.060, 0.345), (0.155, 0.088), name="divider_left"))
    w.add(P.Wall((0.155, 0.088), (0.115, 0.028), name="outlane_cap_left"))
    w.add(P.Wall((0.0, 0.045), (0.105, 0.015), name="outlane_floor_left"))
    m.sling_left = P.Slingshot((0.145, 0.335), (0.205, 0.205), name="sling_left")
    w.add(m.sling_left)
    w.add(P.Wall((0.205, 0.205), (0.168, 0.135), name="sling_back_left"))
    # 右(镜像; 分流墙上端与航道壁留出球道入口)
    w.add(P.Wall((0.505, 0.345), (0.445, 0.088), name="divider_right"))
    w.add(P.Wall((0.445, 0.088), (0.485, 0.028), name="outlane_cap_right"))
    w.add(P.Wall((0.548, 0.045), (0.443, 0.015), name="outlane_floor_right"))
    m.sling_right = P.Slingshot((0.455, 0.335), (0.395, 0.205), name="sling_right")
    w.add(m.sling_right)
    w.add(P.Wall((0.395, 0.205), (0.432, 0.135), name="sling_back_right"))

    # 出球道救援井(仅点亮时收纳球并弹回内道)
    m.outlane_l = P.Saucer((0.090, 0.040), 0.048, "outlane_l",
                           eject_vel=(0.20, 1.7), eject_pos=(0.160, 0.150),
                           capture_speed=2.5, delay=0.5)
    m.outlane_r = P.Saucer((0.510, 0.040), 0.048, "outlane_r",
                           eject_vel=(-0.20, 1.7), eject_pos=(0.440, 0.150),
                           capture_speed=2.5, delay=0.5)
    w.add(m.outlane_l, m.outlane_r)

    # 再入航道滚灯
    m.ro_reentry_l = P.Rollover((0.155, 0.190), 0.030, "reentry_l")
    m.ro_reentry_r = P.Rollover((0.445, 0.190), 0.030, "reentry_r")
    w.add(m.ro_reentry_l, m.ro_reentry_r)

    # ---------- 弹板与中央立柱 ----------
    m.flipper_left = P.Flipper((0.205, 0.118), -0.55, 0.52, name="flipper_left")
    m.flipper_right = P.Flipper((0.395, 0.118), 3.69, 2.62, name="flipper_right")
    w.add(m.flipper_left, m.flipper_right)
    m.center_post = P.Post((0.300, 0.090), 0.013, name="center_post")
    w.add(m.center_post)

    # ---------- 发射杆 ----------
    m.plunger_zone = P.PlungerZone(0.550, 0.596, 0.041, 0.100)
    w.add(m.plunger_zone)

    return m


def reset_medals(meta):
    """奖章靶全部复位立起。"""
    for t in meta.medals:
        t.active = True


def medals_all_down(meta):
    return all(not t.active for t in meta.medals)


def spawn_position():
    """新球投放点: 发射航道上方, 自然落到发射杆上。"""
    return (0.574, 0.300)
