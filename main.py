# -*- coding: utf-8 -*-
"""三维弹球: 太空军校生 —— 现代化重制版 (Ursina 渲染层)

运行:  python main.py
冒烟:  python main.py --smoke   (自动发射+截图后退出, 用于无人工验证)

操作:
    Z / ←           左弹板       / / →          右弹板
    空格 / ↓ (按住)  发射杆蓄力, 松开发射
    X / . / ↑       推台(左/右/上), 连续推台会 TILT
    F1 帮助    F2 新游戏    P 暂停    Esc 退出

注意: 本环境的 Ursina 8.3 Entity.color(colorScale) 不生效,
实体着色统一走 1x1 纯色贴图(tex_color), 文字仍用 color。
"""
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SMOKE = "--smoke" in sys.argv
sys.argv = [a for a in sys.argv if a != "--smoke"]

from ursina import *
from ursina.lights import DirectionalLight, PointLight
from ursina.models.procedural.cylinder import Cylinder
from ursina.shaders import lit_with_shadows_shader, unlit_shader

from spacecadet import config as C
from spacecadet import physics as P
from spacecadet import table as T
from spacecadet import rules as R

from PIL import Image

# ---------------------------------------------------------------- 配色(RGB 0-255)
STEEL = (150, 162, 185)
STEEL_DARK = (74, 82, 100)
CYAN = (64, 224, 255)
ORANGE = (255, 150, 48)
MAGENTA = (255, 80, 200)
GOLD = (255, 200, 60)
GREEN = (70, 230, 130)
YELLOW = (255, 220, 80)
RED = (255, 70, 70)
VIOLET = (170, 100, 255)
WHITE = (255, 255, 255)
DIM = (28, 38, 54)

for _f in ("simhei.ttf", "msyh.ttc", "simsun.ttc"):
    _p = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", _f)
    if os.path.exists(_p):
        import shutil
        if not os.path.exists(os.path.join(HERE, _f)):
            try:
                shutil.copy(_p, os.path.join(HERE, _f))
            except Exception:
                break
        Text.default_font = _f
        break


# ---------------------------------------------------------------- 上色工具
_TEX_CACHE = {}


def tex_color(rgb255):
    """1x1 纯色贴图(缓存)。本版 Ursina 的 Entity.color 失效, 统一用贴图上色。"""
    if rgb255 not in _TEX_CACHE:
        _TEX_CACHE[rgb255] = Texture(Image.new("RGBA", (2, 2), tuple(rgb255)))
    return _TEX_CACHE[rgb255]


# ---------------------------------------------------------------- 程序化贴图
def make_floor_texture():
    """星空台面贴图。"""
    from PIL import ImageDraw, ImageFilter
    W_, H_ = 512, 1024
    img = Image.new("RGBA", (W_, H_), (8, 13, 34, 255))
    rnd = random.Random(7)
    for _ in range(9):
        x, y = rnd.randint(0, W_), rnd.randint(0, H_)
        r = rnd.randint(60, 200)
        c = rnd.choice([(40, 70, 160), (90, 40, 150), (20, 90, 130)])
        neb = Image.new("RGBA", (W_, H_), (0, 0, 0, 0))
        ImageDraw.Draw(neb, "RGBA").ellipse(
            [x - r, y - r * 2 // 3, x + r, y + r * 2 // 3], fill=c + (40,))
        img = Image.alpha_composite(img, neb.filter(ImageFilter.GaussianBlur(30)))
    d = ImageDraw.Draw(img, "RGBA")
    for _ in range(220):
        x, y = rnd.randint(0, W_), rnd.randint(0, H_)
        s = rnd.choice([1, 1, 1, 2])
        b = rnd.randint(120, 255)
        d.ellipse([x, y, x + s, y + s], fill=(b, b, min(255, b + 20), 255))

    def uv(px, py):
        return (px / 0.62 * W_, (1 - py / 1.22) * H_)

    for (bx, by) in [(0.245, 0.845), (0.355, 0.845), (0.30, 0.735)]:
        x, y = uv(bx, by)
        r = 46
        d.ellipse([x - r, y - r, x + r, y + r], outline=(70, 200, 230, 90), width=3)
    x, y = uv(0.30, 0.9)
    d.ellipse([x - 120, y - 60, x + 120, y + 60], outline=(120, 90, 220, 60), width=4)
    x, y = uv(0.30, 0.30)
    d.ellipse([x - 70, y - 70, x + 70, y + 70], outline=(90, 130, 230, 70), width=3)
    d.ellipse([x - 44, y - 44, x + 44, y + 44], outline=(230, 160, 60, 80), width=3)
    return Texture(img)


def make_backglass_texture():
    from PIL import ImageDraw
    W_, H_ = 512, 256
    img = Image.new("RGB", (W_, H_), (10, 14, 40))
    d = ImageDraw.Draw(img)
    for y in range(H_):
        t = max(0.0, 1 - y / (H_ * 0.55))
        d.line([(0, y), (W_, y)], fill=(int(10 + 55 * t), int(14 + 8 * t),
                                        int(40 + 75 * t)))
    rnd = random.Random(3)
    for _ in range(150):
        x, y = rnd.randint(0, W_), rnd.randint(0, H_)
        s = rnd.choice([1, 1, 2])
        b = rnd.randint(100, 255)
        d.ellipse([x, y, x + s, y + s], fill=(b, b, 255 - b // 3))
    d.ellipse([W_ * 0.82, 148, W_ * 0.82 + 52, 196], fill=(255, 232, 150))
    return Texture(img)


# ---------------------------------------------------------------- 应用
app = Ursina(title="三维弹球:太空军校生(重制版)", borderless=False,
             fullscreen=False, vsync=True, development_mode=False)
window.size = (1280, 800)
window.color = color.rgb(4, 6, 14)
try:
    base.setBackgroundColor(0.016, 0.024, 0.055)
except Exception:
    pass
if hasattr(window, "fps_counter") and window.fps_counter:
    window.fps_counter.enabled = False
# 纯 2D 俯视: 正交投影, 镜头从正上方直射台面中心, 屏幕上方 = 台顶
camera.orthographic = True
camera.fov = 1.42               # 正交模式下为竖直视野(世界单位), 约等于整张球台
camera.position = (0.30, 1.2, 0.575)
camera.rotation = (90, 0, 0)

CYL_SEGS = 36


def cyl():
    """每次新建圆柱网格。注意: Mesh 是 NodePath, 共享实例会被最后一个
    使用者 reparent 抢走, 之前的实体将丢失几何体, 必须逐实体实例化。"""
    return Cylinder(resolution=CYL_SEGS)


def make_sphere(u=24, v=16):
    """高精度 UV 球网格(平滑法线), 替代低模 icosphere。
    注意与 cyl() 同理: 每个实体必须独立调用生成, 不可共享。"""
    verts, tris, norms, uvs = [], [], [], []
    for i in range(v + 1):
        theta = math.pi * i / v
        for j in range(u):
            phi = 2 * math.pi * j / u
            x, y, z = (math.sin(theta) * math.cos(phi),
                       math.cos(theta),
                       math.sin(theta) * math.sin(phi))
            verts.append(Vec3(x * 0.5, y * 0.5, z * 0.5))
            norms.append(Vec3(x, y, z))
            uvs.append((j / u, i / v))
    for i in range(v):
        for j in range(u):
            a = i * u + j
            b = i * u + (j + 1) % u
            c = (i + 1) * u + (j + 1) % u
            d = (i + 1) * u + j
            tris.extend(((a, b, c), (a, c, d)))
    return Mesh(vertices=verts, triangles=tris, normals=norms, uvs=uvs,
                mode="triangle")

table_root = Entity()
meta = T.build_table()
world = meta.world

# ---- 光照
AmbientLight(color=color.rgba(95, 100, 125, 255))
sun = DirectionalLight(shadows=True)
sun.position = (0.35, 1.6, -0.55)
sun.look_at(Vec3(0.2, 0, 0.62))
PointLight(color=color.rgba(60, 160, 220, 255), position=(0.12, 0.5, 0.85))
PointLight(color=color.rgba(230, 130, 60, 255), position=(0.5, 0.42, 0.25))

# ---- 台面
Entity(parent=table_root, model="cube", scale=(0.63, 0.02, 1.23),
       position=(0.30, -0.012, 0.575), texture=make_floor_texture(),
       shader=lit_with_shadows_shader)
Entity(parent=table_root, model="cube", scale=(0.74, 0.05, 1.34),
       position=(0.30, -0.045, 0.575), texture=tex_color(STEEL_DARK),
       shader=lit_with_shadows_shader)
Entity(parent=table_root, model="cube", scale=(0.72, 0.34, 0.03),
       position=(0.30, 0.17, 1.24), texture=make_backglass_texture(),
       shader=lit_with_shadows_shader)


def accent_of(wall):
    n = wall.name
    if "sling" in n:
        return ORANGE
    if "medal" in n and "back" not in n:
        return GOLD
    if "orbit" in n or "ypocket" in n:
        return VIOLET
    if "gpocket" in n:
        return GREEN
    return CYAN


for wl in world.walls:
    dx, dy = wl.p2.x - wl.p1.x, wl.p2.y - wl.p1.y
    L = math.hypot(dx, dy)
    ang = -math.degrees(math.atan2(dy, dx))
    mx, mz = (wl.p1.x + wl.p2.x) / 2, (wl.p1.y + wl.p2.y) / 2
    h = 0.012 if isinstance(wl, P.OneWayGate) else 0.03
    Entity(parent=table_root, model="cube", scale=(L + 0.008, h, 0.016),
           position=(mx, h / 2, mz), rotation_y=ang, texture=tex_color(STEEL),
           shader=lit_with_shadows_shader)
    Entity(parent=table_root, model="cube", scale=(L + 0.002, 0.007, 0.019),
           position=(mx, h + 0.003, mz), rotation_y=ang,
           texture=tex_color(VIOLET if isinstance(wl, P.OneWayGate)
                             else accent_of(wl)),
           shader=unlit_shader)

# ---- 缓冲器
bumper_ents = []
BUMP_COLS = [CYAN, ORANGE, MAGENTA]
for i, b in enumerate(meta.bumpers):
    Entity(parent=table_root, model=cyl(), scale=(0.066, 0.05, 0.066),
           position=(b.c.x, 0.025, b.c.y), texture=tex_color(STEEL_DARK),
           shader=lit_with_shadows_shader)
    cap = Entity(parent=table_root, model=cyl(), scale=(0.052, 0.055, 0.052),
                 position=(b.c.x, 0.027, b.c.y), texture=tex_color(BUMP_COLS[i]),
                 shader=unlit_shader)
    Entity(parent=table_root, model=cyl(), scale=(0.072, 0.012, 0.072),
           position=(b.c.x, 0.006, b.c.y), texture=tex_color((40, 46, 62)),
           shader=unlit_shader)
    bumper_ents.append(cap)


def flash_bumper(idx):
    cap = bumper_ents[idx]
    orig = cap.scale
    cap.texture = tex_color(WHITE)
    cap.animate_scale(orig * Vec3(1.25, 1.5, 1.25), duration=0.07,
                      curve=curve.out_quad)
    invoke(lambda: cap.animate_scale(orig, duration=0.18), delay=0.07)
    invoke(lambda: setattr(cap, "texture", tex_color(BUMP_COLS[idx])), delay=0.1)


# ---- 降落靶 / 任务靶
medal_ents = []
for t in meta.medals:
    dx, dy = t.p2.x - t.p1.x, t.p2.y - t.p1.y
    ang = -math.degrees(math.atan2(dy, dx))
    Entity(parent=table_root, model="cube",
           scale=(math.hypot(dx, dy), 0.026, 0.011),
           position=((t.p1.x + t.p2.x) / 2, 0.024, (t.p1.y + t.p2.y) / 2),
           rotation_y=ang, texture=tex_color(STEEL_DARK),
           shader=lit_with_shadows_shader)
    e = Entity(parent=table_root, model="cube",
               scale=(math.hypot(dx, dy) * 0.92, 0.028, 0.008),
               position=((t.p1.x + t.p2.x) / 2, 0.026, (t.p1.y + t.p2.y) / 2),
               rotation_y=ang, texture=tex_color(GOLD), shader=unlit_shader)
    medal_ents.append(e)

mission_ents = []
for t in meta.missions:
    my = (t.p1.y + t.p2.y) / 2
    Entity(parent=table_root, model="cube", scale=(0.014, 0.03, t.p2.y - t.p1.y + 0.008),
           position=(t.p1.x + 0.003, 0.024, my), texture=tex_color(STEEL_DARK),
           shader=lit_with_shadows_shader)
    e = Entity(parent=table_root, model="cube", scale=(0.008, 0.032, t.p2.y - t.p1.y),
               position=(t.p1.x - 0.003, 0.026, my), texture=tex_color(MAGENTA),
               shader=unlit_shader)
    mission_ents.append(e)


# ---- 弹板
def make_flipper(fl):
    root = Entity(parent=table_root, position=(fl.pivot.x, 0.02, fl.pivot.y))
    Entity(parent=root, model="cube", scale=(C.FLIPPER_LEN, 0.021, 0.023),
           position=(C.FLIPPER_LEN / 2, 0, 0), texture=tex_color((216, 222, 234)),
           shader=lit_with_shadows_shader)
    Entity(parent=root, model=make_sphere(18, 12),
           scale=(C.FLIPPER_R0 * 2, 0.024, C.FLIPPER_R0 * 2),
           texture=tex_color((196, 204, 220)), shader=lit_with_shadows_shader)
    Entity(parent=root, model=make_sphere(18, 12), position=(C.FLIPPER_LEN, 0, 0),
           scale=(C.FLIPPER_R1 * 2.4, 0.021, C.FLIPPER_R1 * 2.4),
           texture=tex_color(ORANGE), shader=lit_with_shadows_shader)
    return root


flip_l_ent = make_flipper(meta.flipper_left)
flip_r_ent = make_flipper(meta.flipper_right)

post_ent = Entity(parent=table_root, model=cyl(), scale=(0.026, 0.05, 0.026),
                  position=(meta.center_post.c.x, 0.025, meta.center_post.c.y),
                  texture=tex_color(RED), shader=unlit_shader, enabled=False)

# ---- 收纳井 / 滚灯
SAUCER_COL = {"yellow": YELLOW, "green": GREEN, "hyperspace": CYAN,
              "outlane_l": YELLOW, "outlane_r": YELLOW}
saucer_ents = {}
for s in world.zones:
    if isinstance(s, P.Saucer):
        saucer_ents[s.name] = Entity(
            parent=table_root, model=cyl(), scale=(s.r * 2.2, 0.006, s.r * 2.2),
            position=(s.c.x, 0.004, s.c.y), texture=tex_color(SAUCER_COL[s.name]),
            shader=unlit_shader)

rollover_ents = {}
ROLLOVER_DIM = DIM
for z in world.zones:
    if isinstance(z, P.Rollover):
        rollover_ents[z.name] = Entity(
            parent=table_root, model=cyl(), scale=(z.r * 1.6, 0.004, z.r * 1.6),
            position=(z.c.x, 0.004, z.c.y), texture=tex_color(ROLLOVER_DIM),
            shader=unlit_shader)

plunger = Entity(parent=table_root, model=cyl(), scale=(0.030, 0.016, 0.030),
                 position=(0.574, 0.009, 0.026), texture=tex_color(RED),
                 shader=unlit_shader)
# 停靠位光环: 提示球的发射等待位置
Entity(parent=table_root, model=cyl(), scale=(0.040, 0.004, 0.040),
       position=(0.574, 0.003, 0.054), texture=tex_color((120, 60, 60)),
       shader=unlit_shader)

# ---- 球与拖尾
ball_ents = {}
trails = {}
trail_prev = {}


def ball_entity():
    return Entity(parent=table_root, model=make_sphere(26, 17),
                  scale=(0.0285, 0.0285, 0.0285),
                  texture=tex_color((228, 231, 238)),
                  shader=lit_with_shadows_shader)


def trail_for(bid):
    # 渐远渐小的淡蓝拖尾(近球大、远球小), 避免等大黑点
    trails[bid] = [Entity(parent=table_root, model="icosphere",
                          scale=(0.016 * (1.0 - i * 0.11),
                                 0.008, 0.016 * (1.0 - i * 0.11)),
                          texture=tex_color((40, 96, 132)), shader=unlit_shader,
                          enabled=False)
                   for i in range(7)]


def drop_ball_ent(bid):
    trail_prev.pop(bid, None)
    if bid in ball_ents:
        destroy(ball_ents.pop(bid))
    if bid in trails:
        for e in trails.pop(bid):
            destroy(e)


# ---------------------------------------------------------------- HUD
# 本版 Ursina 的 Text 颜色通道失效(渲染恒白), 文字一律用 PIL 渲染成
# 彩色贴图(带透明通道)贴在 quad 上, 颜色完全可控。
from PIL import ImageDraw, ImageFont

FONT_PATH = os.path.join(HERE, "simhei.ttf")
_label_cache = {}


def label_texture(text, rgb, px=64):
    key = (text, rgb, px)
    if key in _label_cache:
        return _label_cache[key]
    font = ImageFont.truetype(FONT_PATH, px)
    measure = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    box = measure.textbbox((0, 0), text, font=font)
    w, h = max(1, box[2] - box[0]), max(1, box[3] - box[1])
    # 不透明深色底: 透明贴图会进透明渲染队列被 3D 墙体盖住,
    # 不透明则与普通实体同队列, 配合 setBin 画在场景之上
    img = Image.new("RGBA", (w + 16, h + 16), (8, 10, 22, 255))
    ImageDraw.Draw(img).text((8 - box[0], 8 - box[1]), text, font=font,
                             fill=tuple(rgb) + (255,))
    tex = Texture(img)
    _label_cache[key] = (tex, w + 16, h + 16)
    return _label_cache[key]


class Label:
    """贴图文字标签。height 为单行高度(UI 单位), 多行文本自动按行数增高。"""

    def __init__(self, parent, pos, height=0.03, rgb=(255, 255, 255), px=64,
                 pivot="center"):
        self.base_pos = Vec3(pos[0], pos[1], 0)   # 注意: Vec3 两参构造语义异常, 必须传满 3 个
        self.height, self.px, self.pivot = height, px, pivot
        self.rgb = rgb
        self.e = Entity(parent=parent, model="quad", position=self.base_pos,
                        enabled=False)

    def set(self, text, rgb=None):
        if rgb is not None:
            self.rgb = rgb
        if not text:
            self.e.enabled = False
            return
        tex, w, h = label_texture(text, self.rgb, self.px)
        n_lines = text.count("\n") + 1
        sy = self.height * n_lines
        sx = sy * w / h
        self.e.texture = tex
        self.e.scale = Vec3(sx, sy, 1)
        x = self.base_pos.x
        if self.pivot == "left":
            x += sx / 2
        elif self.pivot == "right":
            x -= sx / 2
        self.e.position = Vec3(x, self.base_pos.y, 0)
        self.e.enabled = True


hud = Entity(parent=camera.ui)
# 让 HUD(文字贴图/指示灯/油量条)绘制在 3D 场景之上:
# quad 贴图默认会被台面霓虹等 3D 元素盖住, 固定渲染序+关深度测试可根治
try:
    hud.setBin("fixed", 10)
    hud.setDepthTest(False)
    hud.setDepthWrite(False)
except Exception:
    pass
title_l = Label(hud, (0, 0.475), 0.040, (150, 215, 250), px=80)
title_l.set("SPACE CADET · 太空军校生")
score_l = Label(hud, (-0.62, 0.40), 0.043, (120, 235, 255), pivot="left")
hi_l = Label(hud, (-0.62, 0.355), 0.026, (140, 150, 180), pivot="left")
mult_l = Label(hud, (-0.62, 0.315), 0.030, (255, 200, 60), pivot="left")
rank_l = Label(hud, (0.62, 0.40), 0.032, (255, 200, 90), pivot="right")
ball_l = Label(hud, (0.62, 0.355), 0.026, (160, 170, 195), pivot="right")
mission_l = Label(hud, (0, 0.40), 0.030, (255, 240, 170))
mission_sub_l = Label(hud, (0, 0.365), 0.023, (170, 190, 220))
fuel_bar_bg = Entity(parent=hud, model="cube", scale=(0.28, 0.012, 1),
                     position=(0, 0.335), texture=tex_color((40, 50, 70)))
fuel_bar = Entity(parent=hud, model="cube", scale=(0.28, 0.009, 1),
                  position=(-0.14, 0.335), origin=(-0.5, 0), texture=tex_color(GREEN))
hyper_dots = [Entity(parent=hud, model="circle", scale=0.018,
                     position=(-0.55 + i * 0.03, -0.42), texture=tex_color(DIM))
              for i in range(5)]
Label(hud, (-0.64, -0.412), 0.023, (120, 210, 240)).set("超空间")
medal_dot = Entity(parent=hud, model="circle", scale=0.018, position=(-0.34, -0.42),
                   texture=tex_color(DIM))
Label(hud, (-0.43, -0.412), 0.023, (255, 210, 90)).set("奖章")
kicker_dot = Entity(parent=hud, model="circle", scale=0.018, position=(-0.16, -0.42),
                    texture=tex_color(DIM))
Label(hud, (-0.25, -0.412), 0.023, (255, 220, 80)).set("救援")
Label(hud, (0, -0.475), 0.021, (110, 120, 150)).set(
    "Z/← 左弹板   /或→ 右弹板   空格蓄力发射   X . ↑ 推台   F1 帮助")

toast_l = Label(hud, (0, 0.10), 0.055, (255, 255, 255), px=96)
toast_sub_l = Label(hud, (0, 0.05), 0.026, (200, 220, 255))

# 结束/帮助/暂停画面: 纯文字悬浮(全屏背景方块会盖住 HUD, 不可用)
overlay_title_l = Label(hud, (0, 0.16), 0.065, (255, 230, 140), px=96)
overlay_body_l = Label(hud, (0, 0.0), 0.026, (190, 205, 235))

HELP_LINES = ("操作说明\n\n"
              "Z 或 ←          左弹板\n"
              "/ 或 →          右弹板\n"
              "空格或 ↓ 按住    发射杆蓄力, 松开发射\n"
              "X / . / ↑       推台(小心 TILT 倾台!)\n\n"
              "玩法提示\n"
              "· 击中任务靶开启任务, 在燃料耗尽前完成目标\n"
              "· 集齐一组奖章降落靶 → 奖章灯升级, 全场倍率提升\n"
              "· 左侧发射坡道单向通往台顶; 黄/绿虫洞互相传送\n"
              "· 超空间滑道 5 级: 立柱 → 救援 → 多球\n"
              "· 完成任务数决定军衔晋升(军校生→舰队上将)\n\n"
              "F1 关闭    F2 新游戏    P 暂停    Esc 退出")

toast_state = {"t": 0.0, "showing": False}
TOAST_RGB = {"info": (200, 230, 255), "good": (130, 255, 170),
             "warn": (255, 130, 130), "rank": (255, 215, 110),
             "mission": (170, 220, 255)}


def show_toast(text, sub, kind):
    toast_l.set(text, rgb=TOAST_RGB.get(kind, (255, 255, 255)))
    toast_sub_l.set(sub)
    toast_state["t"] = 2.4
    toast_state["showing"] = True


# ---------------------------------------------------------------- 游戏接线
def on_rules_event(name, payload):
    if name == "toast":
        show_toast(*payload)
    elif name == "bumper":
        if payload and payload[-1].isdigit():
            flash_bumper(int(payload[-1]))
    elif name == "flash":
        e = rollover_ents.get(payload)
        if e:
            e.texture = tex_color(WHITE)
            invoke(lambda: setattr(e, "texture", tex_color(ROLLOVER_DIM)),
                   delay=0.4)
    elif name == "medal_bank":
        for e in medal_ents:
            e.texture = tex_color(WHITE)
        invoke(reset_medal_visuals, delay=0.3)
    elif name == "tilt":
        toast_l.set("TILT!", rgb=(255, 70, 70))
        toast_sub_l.set("弹板失效直至丢球")
        toast_state["t"] = 3.0
        toast_state["showing"] = True
    elif name == "gameover":
        show_gameover()


def reset_medal_visuals():
    for e in medal_ents:
        e.texture = tex_color(GOLD)


game = R.Game(on_event=on_rules_event)
world.armed_fn = lambda name: game.kicker_lit

HI_FILE = os.path.join(HERE, "highscore.json")
if os.path.exists(HI_FILE):
    try:
        with open(HI_FILE, encoding="utf-8") as f:
            game.hiscore = int(json.load(f).get("hiscore", 0))
    except Exception:
        pass


def save_hiscore():
    try:
        with open(HI_FILE, "w", encoding="utf-8") as f:
            json.dump({"hiscore": game.hiscore}, f)
    except Exception:
        pass


def set_overlay(title, body):
    # 注意: 事后给 Text 赋 .color 会走 colorScale(本版失效变白), 颜色一律在构造时定死
    overlay_title_l.set(title)
    overlay_body_l.set(body)


def hide_overlay():
    overlay_title_l.set("")
    overlay_body_l.set("")


def show_gameover():
    if game.score > game.hiscore:
        game.hiscore = game.score
        save_hiscore()
    # 清掉可能残留的 toast(如"任务中止"), 避免与结束画面文字重叠
    toast_l.set("")
    toast_sub_l.set("")
    toast_state["showing"] = False
    body = ("最终得分  %s\n%s  %s\n\n按 F2 / 回车 重新开始" %
            (R.fmt(game.score), game.rank_name()[0], game.rank_name()[1]))
    if game.score >= game.hiscore and game.score > 0:
        body += "\n★ 新纪录!"
    set_overlay("游戏结束", body)


def spawn_ball_at_plunger():
    world.add_ball(T.spawn_position())


def new_game():
    game.reset()
    world.clear_balls()
    for bid in list(ball_ents):
        drop_ball_ent(bid)
    T.reset_medals(meta)
    hide_overlay()
    paused[0] = False
    help_open[0] = False
    spawn_ball_at_plunger()
    show_toast("第 1 球", "军衔 军校生 — 击中任务靶开启任务", "info")


paused = [False]
help_open = [False]
charge = {"v": 0.0, "holding": False}
medal_reset_pending = [False]
prev_state = [None]


# ---------------------------------------------------------------- 主循环
def update():
    dt = min(time.dt, 0.05)
    if paused[0]:
        return
    game.tick(dt)

    if prev_state[0] != game.state:
        if game.state == "ready":
            T.reset_medals(meta)
            medal_reset_pending[0] = False
        prev_state[0] = game.state

    meta.flipper_left.engaged = bool(held_keys["z"] or held_keys["left arrow"])
    meta.flipper_right.engaged = bool(held_keys["slash"] or held_keys["right arrow"])
    meta.flipper_left.force_down = game.tilted
    meta.flipper_right.force_down = game.tilted

    # 发射杆蓄力(不检查 state: 弱发射回落后球已在杆上, 任何状态都允许重新蓄力)
    if game.plunger_ball is not None:
        if held_keys["space"] or held_keys["down arrow"]:
            charge["holding"] = True
            charge["v"] = min(1.0, charge["v"] + dt / C.PLUNGER_TMAX)
            plunger.y = 0.010 - charge["v"] * 0.010
        elif charge["holding"]:
            speed = C.PLUNGER_VMIN + charge["v"] * (C.PLUNGER_VMAX - C.PLUNGER_VMIN)
            b = game.launch()
            if b is not None:
                b.vel = P.Vec2(0, speed)
            charge["holding"] = False
            charge["v"] = 0.0
            plunger.y = 0.010
        # 看门狗: 任何未知路径导致 play 状态下球停在发射杆, 1.5 秒后强制恢复
        if game.state == "play":
            charge["wd"] = charge.get("wd", 0.0) + dt
            if charge["wd"] > 1.5:
                game.state = "ready"
                charge["wd"] = 0.0
                print("[watchdog] play 状态下球在发射杆, 已恢复 ready")
        else:
            charge["wd"] = 0.0
    else:
        charge["v"] = 0.0
        charge["holding"] = False

    if game.state == "ready" and not world.balls and game.plunger_ball is None:
        spawn_ball_at_plunger()

    if game.state in ("ready", "play"):
        for evt in world.advance(dt):
            game.handle(evt, meta)

    if T.medals_all_down(meta) and not medal_reset_pending[0]:
        medal_reset_pending[0] = True
        invoke(_reset_medals_later, delay=1.5)

    if game.spawn_requests:
        game.spawn_requests.clear()
        world.add_ball((0.35, 0.50), (0.1, 1.4))
        world.add_ball((0.16, 1.00), (0.5, -0.3))
        game.spawn_multiball()

    alive = {b.id for b in world.balls}
    for bid in list(ball_ents):
        if bid not in alive:
            drop_ball_ent(bid)
    for b in world.balls:
        if b.id not in ball_ents:
            ball_ents[b.id] = ball_entity()
            trail_for(b.id)
        e = ball_ents[b.id]
        pos = Vec3(b.pos.x, 0.0155, b.pos.y)
        e.position = pos
        ts = trails.get(b.id)
        if ts:
            if not b.held and b.speed() > 1.2:
                # 拖尾记录上一帧位置(滞后一帧), 且高度低于球心——
                # 拖尾球绝不与球体重合, 否则透明排序会让深色拖尾
                # 盖住银球, 球在快速移动时整体发黑
                ghost = trail_prev.get(b.id, Vec3(b.pos.x, 0.010, b.pos.y))
                ghost = Vec3(ghost.x, 0.010, ghost.z)
                for i in range(len(ts) - 1, 0, -1):
                    ts[i].position = ts[i - 1].position
                    ts[i].enabled = True
                ts[0].position = ghost
                ts[0].enabled = True
                trail_prev[b.id] = pos
            else:
                for t_ in ts:
                    t_.enabled = False
                trail_prev.pop(b.id, None)

    flip_l_ent.rotation_y = -math.degrees(meta.flipper_left.angle)
    flip_r_ent.rotation_y = -math.degrees(meta.flipper_right.angle)

    for t, e in zip(meta.medals, medal_ents):
        e.y = 0.026 if t.active else 0.007
    post_ent.enabled = game.center_post
    meta.center_post.active = game.center_post
    for s in world.zones:
        if isinstance(s, P.Saucer) and s.name in saucer_ents:
            saucer_ents[s.name].texture = tex_color(
                WHITE if s.holding is not None else SAUCER_COL[s.name])

    update_hud()

    if toast_state["showing"]:
        toast_state["t"] -= dt
        if toast_state["t"] <= 0:
            toast_state["showing"] = False
            toast_l.set("")
            toast_sub_l.set("")

    smoke_update(dt)


def _reset_medals_later():
    T.reset_medals(meta)
    medal_reset_pending[0] = False


def update_hud():
    score_l.set("得分  %s" % R.fmt(game.score))
    hi_l.set("最高  %s" % R.fmt(max(game.hiscore, game.score)))
    mult_l.set("倍率 ×%d%s" % (
        game.multiplier, "  重力×2" if game.gravity_time > 0 else ""))
    rank_l.set("%s %s" % game.rank_name())
    ball_l.set("球 %d/%d   任务 %d/%s" % (
        game.ball_num, game.total_balls, game.rank_done,
        R.MISSIONS_NEEDED[game.rank] if game.rank < len(R.MISSIONS_NEEDED) else "—"))
    if game.mission:
        mission_l.set("任务  %s  (%d/%d)" % (
            game.mission["name"], game.mission_progress, game.mission["prog"]))
        mission_sub_l.set(game.mission["obj"])
        fuel_bar.scale_x = 0.28 * max(0.0, min(1.0, game.fuel / 60.0))
        fuel_bar.texture = tex_color(GREEN if game.fuel > 15 else RED)
        fuel_bar_bg.enabled = fuel_bar.enabled = True
    else:
        mission_l.set("击中任务靶以开启任务" if game.state == "play" else "")
        mission_sub_l.set("")
        fuel_bar_bg.enabled = fuel_bar.enabled = False
    for i, d in enumerate(hyper_dots):
        d.texture = tex_color(CYAN if i < game.hyper_lights else DIM)
    medal_dot.texture = tex_color([DIM, (80, 130, 255), RED, MAGENTA][game.medal_stage])
    kicker_dot.texture = tex_color(YELLOW if game.kicker_lit else DIM)


# ---------------------------------------------------------------- 冒烟测试
smoke = {"t": 0.0, "phase": 1, "done": False}
SMOKE_SHOTS = []


def smoke_update(dt):
    if not SMOKE or smoke["done"]:
        return
    smoke["t"] += dt
    t = smoke["t"]
    # 阶段1: 弱发射(蓄力0.15s, 球出不了通道) —— 回归弱发射死锁修复
    if 0.6 < t <= 0.75:
        held_keys["space"] = 1
    elif 0.75 < t <= 1.0 and smoke["phase"] == 1:
        held_keys["space"] = 0
        smoke["phase"] = 2
    # 阶段2: 等球回落发射杆后满力发射
    if 2.2 < t <= 3.4 and smoke["phase"] == 2:
        held_keys["space"] = 1
    elif t > 3.4 and smoke["phase"] == 2:
        held_keys["space"] = 0
        smoke["phase"] = 3
        print("[smoke] weak-launch relaunch state=%s held=%s" %
              (game.state, game.plunger_ball is not None))
    if smoke["phase"] == 3:
        if random.random() < 0.04:
            held_keys["z"] = 1
        if random.random() < 0.04:
            held_keys["slash"] = 1
        if random.random() < 0.10:
            held_keys["z"] = held_keys["slash"] = 0
    # 阶段4: 强制游戏结束, 验证结束画面(黑屏回归)
    if 4.5 < t <= 4.6 and smoke["phase"] == 3:
        smoke["phase"] = 4
        game.state = "play"
        game.balls_in_play = 1
        game.ball_num = game.total_balls
        for b in list(world.balls):
            game.handle(("drain", b), meta)
            world.remove_ball(b)
        print("[smoke] forced gameover state=%s overlay=%s" %
              (game.state, overlay_title_l.e.enabled))
    for ts, name in [(2.0, "smoke_weak.png"), (4.2, "smoke_play.png"),
                     (5.4, "smoke_over.png")]:
        if t >= ts and name not in SMOKE_SHOTS:
            SMOKE_SHOTS.append(name)
            try:
                base.win.saveScreenshot(name)
                for b in world.balls:
                    print("[smoke] ball at (%.2f, %.2f) v=%.1f held=%s" %
                          (b.pos.x, b.pos.y, b.speed(), b.held))
                print("[smoke] saved", os.path.join(HERE, name))
            except Exception as e:
                print("[smoke] screenshot failed:", e)
    if t > 6.6:
        smoke["done"] = True
        print("[smoke] score=%s rank=%s balls=%d" %
              (game.score, game.rank_name()[0], len(world.balls)))
        application.quit()


# ---------------------------------------------------------------- 输入
def input(key):
    if key == "f2":
        new_game()
        return
    if game.state == "gameover" and key in ("enter", "space", "return"):
        new_game()
        return
    if key == "f1":
        help_open[0] = not help_open[0]
        if help_open[0]:
            set_overlay("帮助", HELP_LINES)
        elif game.state == "gameover":
            show_gameover()
        else:
            hide_overlay()
        return
    if key == "p" and game.state != "gameover":
        paused[0] = not paused[0]
        if paused[0]:
            set_overlay("暂停", "按 P 继续")
        elif help_open[0]:
            set_overlay("帮助", HELP_LINES)
        else:
            hide_overlay()
        return
    if key == "escape":
        application.quit()
        return
    if game.state == "play" and not game.tilted:
        if key == "x":
            world.nudge((0.30, 0.22))
            game.nudge("left")
        elif key in ("period", "."):
            world.nudge((-0.30, 0.22))
            game.nudge("right")
        elif key == "up arrow":
            world.nudge((0.0, 0.40))
            game.nudge("up")


# ---------------------------------------------------------------- 启动
new_game()
if SMOKE:
    print("[smoke] running...")
app.run()
