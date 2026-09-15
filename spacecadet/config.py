# -*- coding: utf-8 -*-
"""全局常量配置。

物理坐标约定(俯视 2D 平面):
    x 向右, y 指向球台顶端(远离玩家), 单位: 米。
真实弹球台约 0.54m x 1.10m, 球直径 27mm; 这里按相近比例建模。
重力取"台面倾斜分量"的等效值并适度调大, 以贴近原作手感。
"""

G = 3.4              # 台面等效重力加速度 (m/s^2)
VMAX = 4.8           # 球速上限 (m/s), 防穿透与失控
SUB_DT = 1.0 / 480.0 # 物理固定子步长
AIR_DRAG = 0.10      # 线性阻尼 (1/s)
BALL_R = 0.014       # 球半径

WALL_E = 0.32        # 墙恢复系数
WALL_MU = 0.02       # 切向摩擦系数
POST_E = 0.55        # 圆柱恢复系数
FLIPPER_E = 0.38     # 弹板恢复系数
FLIPPER_W_UP = 30.0  # 弹板上摆角速度 (rad/s)
FLIPPER_W_DOWN = 20.0
FLIPPER_LEN = 0.088  # 弹板长度
FLIPPER_R0 = 0.016   # 根部半径
FLIPPER_R1 = 0.009   # 尖端半径

BUMPER_KICK = 2.3    # 缓冲器弹出球速
SLING_KICK = 1.9     # 三角弹弓弹出球速

DRAIN_Y = 0.0        # 球心低于此线判为落沟

PLUNGER_VMIN = 1.3   # 发射杆最小/最大出球速度
PLUNGER_VMAX = 4.6
PLUNGER_TMAX = 1.0   # 蓄力满格所需时间 (秒)

# —— 计分 / 规则 ——
SCORE_BUMPER = 500
SCORE_SLING = 25
SCORE_LAUNCH_RAMP = 5000
SCORE_REENTRY = 1500
SCORE_MEDAL_TARGET = 750
SCORE_MEDAL_BANK = 5000
SCORE_MISSION_TARGET = 1000
SCORE_YELLOW_WORMHOLE = 15000
SCORE_GREEN_WORMHOLE = 10000

BALLS_PER_GAME = 3

# 超空间滑道 5 级奖励灯
HYPERSPACE_AWARDS = [
    (25000,  ""),          # 1: 25,000
    (50000,  ""),          # 2: 50,000
    (75000,  "中央立柱升起"),  # 3
    (100000, "出球道救援点亮"), # 4
    (250000, "多球!"),        # 5
]

MULTIPLIER_LADDER = [1, 2, 3, 5]  # 奖章靶组数 → 全场倍率
