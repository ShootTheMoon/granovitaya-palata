# -*- coding: utf-8 -*-
"""러시아 정교회 형태 문법 — 양파돔 · 텐트지붕 · 코코시닉 · 십자가 · 별.

전부 **회전면이거나 다각뿔**이라 파라메트릭 프로파일 하나로 정리된다.
roof._add_grid(P(u,v)) 를 쓸 수도 있지만, 여기서는 정점을 직접 놓는다 —
꼭짓점(r=0)에서 격자면은 축약면이 생기고, 그 축약면이 익스포터 삼각화에서
0 면적 삼각형으로 남아 preflight 에 걸린다. 팬으로 닫는 편이 깨끗하다.

양파돔 프로파일
    핵심 정의는 **돔 최대 직경 > 하부 드럼 직경**이다(아래로 오목하게 오버행).
    이게 없으면 그냥 반구지 양파가 아니다.
    비율은 measured.DOME 의 bulge_ratio(1.382)·height_ratio(1.618) 를 쓴다.
    ⚠ 이 값들은 derived 다 — 2차 출처(Grokipedia)에서 왔고, 같은 출처의
    h/w=1.5~2.0 과는 서로 모순이다(measured.py 주석 참조).
    스케치팹 Onion Dome(a13043fdbf3e46419816c58108e0ef11, CC BY-NC)의 메시
    단면과 대조해 검증한 뒤 measured 로 승격할 것.
"""

import math

import bmesh

import hanok
from kremlin import measured
from kremlin.measured import val

# 양파돔 실루엣 제어점 (t, r/r_drum). t=0 드럼 상단, t=1 꼭짓점.
# Catmull-Rom 으로 잇는다. **오버행이 이 표의 존재 이유다** — t=0.35 에서
# 1.382 로 부풀었다가 t=1 에서 0 으로 수렴하며 첨점을 만든다.
# 처음에 벌징 정점을 t=0.35 에 두고 0.62→1.00, 0.82→0.45 로 이었더니
# **총알 모양**이 나왔다 — 상부가 거의 직선이라 원뿔로 읽힌다.
# 양파는 (a) 벌징이 더 아래에 있고 (b) 벌징이 오래 유지되다가
# (c) 상부에서 오목하게 급히 좁아진 뒤 (d) 가느다란 첨점으로 간다.
ONION_PROFILE = [
    (0.00, 1.000),
    (0.05, 1.105),      # 목: 드럼을 넘어 바로 벌어진다(오버행의 시작)
    (0.26, 1.382),      # 최대 벌징 — 아래쪽에 둔다
    (0.44, 1.330),      # 넓은 채로 유지
    (0.62, 1.045),
    (0.76, 0.660),      # 여기서부터 오목하게 꺾인다
    (0.87, 0.330),
    (0.95, 0.130),
    (1.00, 0.000),      # 첨점
]


# ★ **투구형 돔(шлемовидная глава).** 양파돔이 아니다.
#
# Commons 정면 사진(Dormition-Cathedral_Moscow.jpg)을 직접 재서 확인했다.
# 우스펜스키 대성당의 돔은 폭보다 낮은 반구형에 가깝고 꼭대기만 살짝 뾰족하다.
# 사진 실측: 돔 폭 ≈ 450 px, 돔 높이 ≈ 220 px → **h/w ≈ 0.49**
# (첨탑 목까지 포함해도 0.67). 내가 쓰던 양파돔은 h/w = 1.171 이라 두 배 넘게
# 높았고, 그래서 렌더가 실제 성당과 안 닮았다.
#
# 이건 취향 문제가 아니라 **연대 문제**다. 양파돔은 17세기 이후 형식이고,
# 그 이전(우스펜스키 1479, 아르한겔스키 1508)은 투구형이다.
# 성 바실리(1561)와 후대 성당은 양파돔이 맞다.
HELMET_PROFILE = [
    (0.00, 1.000),
    (0.14, 1.055),      # 드럼보다 아주 조금만 벌어진다
    (0.38, 1.000),
    (0.60, 0.830),
    (0.78, 0.540),
    (0.91, 0.235),
    (1.00, 0.000),
]
HELMET_H_RATIO = 0.62   # 드럼 **직경** 대비 돔 높이. 양파돔은 1.618


def _catmull(pts, t):
    """제어점 [(x, y)] 를 지나는 Catmull-Rom 보간. x 는 오름차순."""
    n = len(pts)
    if t <= pts[0][0]:
        return pts[0][1]
    if t >= pts[-1][0]:
        return pts[-1][1]
    i = 0
    while i < n - 2 and pts[i + 1][0] < t:
        i += 1
    p0 = pts[max(0, i - 1)]
    p1, p2 = pts[i], pts[i + 1]
    p3 = pts[min(n - 1, i + 2)]
    u = (t - p1[0]) / max(1e-9, p2[0] - p1[0])
    u2, u3 = u * u, u * u * u
    return 0.5 * ((2.0 * p1[1])
                  + (-p0[1] + p2[1]) * u
                  + (2.0 * p0[1] - 5.0 * p1[1] + 4.0 * p2[1] - p3[1]) * u2
                  + (-p0[1] + 3.0 * p1[1] - 3.0 * p2[1] + p3[1]) * u3)


def _revolve(bm, cx, cy, z0, prof, seg=24):
    """(r, z) 프로파일을 Z 축으로 돌린다. r=0 인 끝은 팬으로 닫는다.

    prof 는 아래→위 순서. 반환은 (아래 링, 위 링) — 없으면 None.
    """
    rings = []
    apex_top = apex_bot = None
    for r, z in prof:
        if r < 1e-6:
            v = bm.verts.new((cx, cy, z0 + z))
            if not rings:
                apex_bot = v
            else:
                apex_top = v
            rings.append(None)
            continue
        ring = []
        for k in range(seg):
            a = 2.0 * math.pi * k / seg
            ring.append(bm.verts.new(
                (cx + r * math.cos(a), cy + r * math.sin(a), z0 + z)))
        rings.append(ring)

    prev = None
    prev_apex = apex_bot
    for ring in rings:
        if ring is None:
            continue
        if prev is not None:
            for k in range(seg):
                j = (k + 1) % seg
                bm.faces.new((prev[k], prev[j], ring[j], ring[k]))
        elif prev_apex is not None:
            for k in range(seg):
                j = (k + 1) % seg
                bm.faces.new((prev_apex, ring[j], ring[k]))
        prev = ring
    if apex_top is not None and prev is not None:
        for k in range(seg):
            j = (k + 1) % seg
            bm.faces.new((prev[k], prev[j], apex_top))
    return rings


def onion(bm, cx, cy, z0, r_drum, height=None, seg=24, steps=22, shape='onion'):
    """돔. z0 는 드럼 상단. height 를 안 주면 형식별 비율에서 유도한다.

    shape='onion'  17세기 이후. 오버행이 크고 첨점이 길다 (성 바실리 등)
    shape='helmet' 그 이전. 반구에 가깝고 낮다 (우스펜스키 1479, 아르한겔스키 1508)

    **연대에 맞는 형식을 써야 한다.** 15~16세기 성당에 양파돔을 얹으면
    두 배 넘게 높아져서 실제와 안 닮는다 — 첫 렌더가 그랬다.
    """
    prof_tab = HELMET_PROFILE if shape == 'helmet' else ONION_PROFILE
    ratio = (HELMET_H_RATIO if shape == 'helmet'
             else val(measured.DOME, 'height_ratio'))
    if height is None:
        height = 2.0 * r_drum * ratio
    prof = []
    for i in range(steps + 1):
        t = i / float(steps)
        prof.append((r_drum * _catmull(prof_tab, t), height * t))
    _revolve(bm, cx, cy, z0, prof, seg)
    return height


def drum(bm, cx, cy, z0, r, h, seg=24, flutes=0, windows=0, arcade=True):
    """돔 아래 원통 드럼.

    **창이 없는 드럼은 러시아 성당이 아니다.** 드럼은 채광창이 목적이라
    반드시 좁고 긴 창이 둘러 있고, 그 위에 아케이드 띠와 처마가 붙는다.
    통짜 원통으로 두면 성당이 아니라 굴뚝으로 보인다 — 실제로 그렇게 나왔다.

    windows  창 개수 (0 이면 통짜)
    arcade   상단 아케이드 띠 + 처마
    """
    prof = [(r, 0.0), (r, h)]
    if flutes:
        # 홈은 반지름을 각도에 따라 흔드는 대신 **다각형 단면**으로 낸다.
        # 반지름 변조는 노멀이 부드러워 홈이 안 읽힌다.
        seg = flutes * 2
    _revolve(bm, cx, cy, z0, prof, seg)

    if windows:
        wz0, wh = z0 + h * 0.22, h * 0.52
        ww = 2.0 * math.pi * r / windows * 0.34     # 창 폭 (호 길이의 1/3)
        for k in range(windows):
            a = 2.0 * math.pi * k / windows
            _slot(bm, cx + r * math.cos(a), cy + r * math.sin(a),
                  wz0, ww, wh, r * 0.10, a, arch=True)
    if arcade:
        # 상단 아케이드 띠 — 작은 기둥 없이 처마 두 단으로 축약한다.
        # 드럼은 대개 멀리서 보이므로 기둥까지 세우면 삼각형만 먹는다.
        _revolve(bm, cx, cy, z0 + h * 0.80,
                 [(r * 1.06, 0.0), (r * 1.06, h * 0.055),
                  (r * 1.01, h * 0.075)], seg)
        _revolve(bm, cx, cy, z0 + h * 0.94,
                 [(r * 1.09, 0.0), (r * 1.09, h * 0.06)], seg)
    return h


def _slot(bm, px, py, z0, w, h, depth, ang, arch=False):
    """벽면에 파인 좁은 창. **불리언을 쓰지 않는다** — 살짝 파인 박스다.

    ang 은 벽면의 바깥 법선 방향(라디안). 안쪽(-법선)으로 depth 만큼 판다.
    """
    nx, ny = math.cos(ang), math.sin(ang)
    ux, uy = -ny, nx                       # 벽면 접선
    hw = w / 2.0
    body = h * (0.72 if arch else 1.0)

    def prism(z_lo, z_hi, half):
        pts = [(px + ux * -half, py + uy * -half),
               (px + ux * half, py + uy * half)]
        quad = [(pts[0][0], pts[0][1]), (pts[1][0], pts[1][1]),
                (pts[1][0] - nx * depth, pts[1][1] - ny * depth),
                (pts[0][0] - nx * depth, pts[0][1] - ny * depth)]
        a = [bm.verts.new((q[0], q[1], z_lo)) for q in quad]
        b = [bm.verts.new((q[0], q[1], z_hi)) for q in quad]
        bm.faces.new(list(reversed(a)))
        bm.faces.new(b)
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((a[i], a[j], b[j], b[i]))

    prism(z0, z0 + body, hw)
    if arch:
        # 반원 머리 — 계단 3단으로 근사한다. 정식 호를 돌리면 창 하나에
        # 삼각형이 40개씩 들어가는데, 창이 수백 개라 감당이 안 된다.
        for i in range(3):
            t = (i + 0.5) / 3.0
            prism(z0 + body + h * 0.28 * i / 3.0,
                  z0 + body + h * 0.28 * (i + 1) / 3.0,
                  hw * math.sqrt(max(0.0, 1.0 - t * t)))


def tent(bm, cx, cy, z0, r, h, sides=8, flare=0.0):
    """텐트지붕(шатёр). 팔각뿔이 기본.

    크렘린 탑 상부 대부분이 이것이다(Спасская 1624–25 등).
    구조 문법은 **восьмерик на четверике** — 사각 몸통 위 팔각 몸통 위 팔각뿔.
    flare 는 처마를 살짝 내미는 값(0 이면 순수 뿔).
    """
    prof = []
    if flare > 0.0:
        prof.append((r * (1.0 + flare), 0.0))
        prof.append((r, h * 0.06))
    else:
        prof.append((r, 0.0))
    prof.append((0.0, h))
    _revolve(bm, cx, cy, z0, prof, sides)
    return h


def ball(bm, cx, cy, z0, r, seg=12):
    """소구(яблоко) — 돔 꼭대기와 십자가 사이의 금박 구슬."""
    prof = []
    n = 8
    for i in range(n + 1):
        a = math.pi * i / n
        prof.append((r * math.sin(a), r * (1.0 - math.cos(a))))
    _revolve(bm, cx, cy, z0, prof, seg)
    return 2.0 * r


def cross(bm, cx, cy, z0, h, yaw=0.0, t=None):
    """러시아 정교 십자가. 가로대 3개, 맨 아래는 기울어져 있다.

    기울기 방향에는 의미가 있다 — 그리스도의 오른쪽(보는 이 기준 왼쪽)이
    올라간다. 회개한 도둑과 회개하지 않은 도둑을 가리킨다.
    ⚠ 각도는 정경화돼 있지 않다. 25~35도가 통용되나 출처를 못 찾았다.
    """
    t = t or h * 0.045
    c, s = math.cos(yaw), math.sin(yaw)

    def box(u0, u1, z_0, z_1, tilt=0.0):
        """가로 u, 세로 z 평면의 판. yaw 로 돌려 놓는다."""
        pts = [(u0, z_0), (u1, z_0 + tilt), (u1, z_1 + tilt), (u0, z_1)]
        vs = []
        for d in (-t / 2.0, t / 2.0):
            ring = []
            for u, z in pts:
                ring.append(bm.verts.new(
                    (cx + u * c - d * s, cy + u * s + d * c, z0 + z)))
            vs.append(ring)
        a, b = vs
        bm.faces.new(list(reversed(a)))
        bm.faces.new(b)
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((a[i], a[j], b[j], b[i]))

    box(-t / 2.0, t / 2.0, 0.0, h)                       # 기둥
    box(-h * 0.13, h * 0.13, h * 0.80, h * 0.845)        # 명패(가장 짧다)
    box(-h * 0.24, h * 0.24, h * 0.58, h * 0.635)        # 주 가로대(가장 길다)
    # 발받침 — 기울어진 것. tilt 로 오른쪽 끝을 내린다(보는 이 기준 왼쪽이 위).
    box(-h * 0.19, h * 0.19, h * 0.30, h * 0.352, tilt=-h * 0.115)
    return h


def star(bm, cx, cy, z0, span, thick=None, points=5, yaw=0.0):
    """크렘린 루비 별. span 은 날개 끝점 간 거리(3.0~3.75 m).

    **별면은 수직이다.** 처음에 XY 평면(수평)에 눕혔더니 위에서만 별로 보이고
    지상에서는 납작한 마름모로 보였다. 실제 별은 풍향계처럼 수직축으로 돌고,
    사람이 아래에서 올려다보며 별 모양을 본다. 그래서 별면을 세우고
    yaw 로 방향만 돌린다. z0 는 별의 **중심** 높이다.

    입체 오각별 — 앞뒤로 볼록한 이중 피라미드다(평면 별이 아니다).
    스케치팹 CC BY 모델(482e8266fe5b41609a5567196370ff79)로 대체할 수 있으나,
    이쪽이 치수를 실측표에서 바로 먹일 수 있어 기본값으로 둔다.
    """
    R = span / 2.0
    r = R * 0.382                       # 안쪽 반지름. 오각별의 표준 비
    thick = thick if thick is not None else R * 0.30
    c, s = math.cos(yaw), math.sin(yaw)
    n = points * 2
    rim = []
    for k in range(n):
        # 별면 안에서의 각. +Z 가 위로 가는 꼭짓점 하나를 두려고 90도 돌린다.
        a = math.pi / 2.0 + 2.0 * math.pi * k / n
        rad = R if (k % 2 == 0) else r
        u, z = rad * math.cos(a), rad * math.sin(a)     # 별면 좌표 (가로, 세로)
        rim.append(bm.verts.new((cx + u * c, cy + u * s, z0 + z)))
    # 앞뒤 볼록 꼭짓점은 별면의 법선 방향(-s, c)으로 나간다
    nx, ny = -s, c
    front = bm.verts.new((cx + nx * thick, cy + ny * thick, z0))
    back = bm.verts.new((cx - nx * thick, cy - ny * thick, z0))
    for k in range(n):
        j = (k + 1) % n
        bm.faces.new((rim[k], rim[j], front))
        bm.faces.new((rim[j], rim[k], back))
    return 2.0 * thick


def kokoshnik_ring(bm, cx, cy, z0, r, count, w, h, depth=None, phase=0.0):
    """코코시닉 방사 링 — 텐트지붕·드럼 기부를 두르는 **순수 장식**.

    자코마라와 헷갈리면 안 된다. 자코마라는 내부 원통 볼트의 단면을 그대로
    외부에 드러내는 **구조 요소**이고 벽면과 연속된다. 코코시닉은 하중을
    받지 않고 기부에서 벽면과 분리돼 돌출한다("가짜 자코마라").
    16세기에 등장해 17세기에 폭발적으로 유행했다.
    """
    depth = depth or w * 0.30
    for k in range(count):
        a = phase + 2.0 * math.pi * k / count
        ca, sa = math.cos(a), math.sin(a)
        bx, by = cx + r * ca, cy + r * sa
        # 킬형(오지) 아치 — 두 원호가 정점에서 만나 뾰족해진다.
        prof = []
        steps = 7
        for i in range(steps + 1):
            u = -w / 2.0 + w * i / steps
            # 반원 + 첨점 보정
            q = 1.0 - (2.0 * u / w) ** 2
            z = h * (math.sqrt(max(0.0, q)) * 0.82
                     + 0.18 * max(0.0, 1.0 - abs(2.0 * u / w)) ** 0.5)
            prof.append((u, z))
        ring = []
        for d in (0.0, depth):
            side = []
            for u, z in prof:
                side.append(bm.verts.new(
                    (bx + ca * d - sa * u, by + sa * d + ca * u, z0 + z)))
            ring.append(side)
        a_, b_ = ring
        for i in range(steps):
            bm.faces.new((a_[i], a_[i + 1], b_[i + 1], b_[i]))
        # 밑면
        bm.faces.new((a_[0], b_[0], b_[steps], a_[steps]))
    return h


def arcade_belt(bm, p0, p1, z0, h, pitch=1.25, depth=0.34, steps=5):
    """아케이드 열주대(аркатурно-колончатый пояс) — 작은 기둥 + 반원 아치 띠.

    **우스펜스키 대성당에서 가장 알아보기 쉬운 요소다.** 벽 중간 높이를 가로로
    두르며 벽면을 상하로 나눈다. 12세기 블라디미르-수즈달 건축에서 온 것이고,
    피오라반티가 우스펜스키에 그대로 옮겼다. 이게 없으면 흰 상자로 보인다 —
    실제로 첫 렌더가 그랬다.

    구성: 아래 선반(폴리스) → 작은 기둥 열 → 반원 아치 → 위 처마.
    p0→p1 이 한 면이고, 왼쪽 법선 방향으로 depth 만큼 내민다.
    """
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    if L < pitch:
        return 0
    u = (dx / L, dy / L)
    v = (-u[1], u[0])
    n = max(1, int(round(L / pitch)))
    step = L / n
    col_h = h * 0.58
    shelf = h * 0.10

    def slab(s0, s1, d0, d1, zl, zh):
        pts = [(p0[0] + u[0] * s0 + v[0] * d0, p0[1] + u[1] * s0 + v[1] * d0),
               (p0[0] + u[0] * s1 + v[0] * d0, p0[1] + u[1] * s1 + v[1] * d0),
               (p0[0] + u[0] * s1 + v[0] * d1, p0[1] + u[1] * s1 + v[1] * d1),
               (p0[0] + u[0] * s0 + v[0] * d1, p0[1] + u[1] * s0 + v[1] * d1)]
        a = [bm.verts.new((q[0], q[1], zl)) for q in pts]
        b = [bm.verts.new((q[0], q[1], zh)) for q in pts]
        bm.faces.new(list(reversed(a)))
        bm.faces.new(b)
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((a[i], a[j], b[j], b[i]))

    slab(0.0, L, 0.0, depth * 1.15, z0, z0 + shelf)                  # 아래 선반
    for i in range(n + 1):                                           # 기둥
        s = min(L, step * i)
        px = p0[0] + u[0] * s
        py = p0[1] + u[1] * s
        _revolve(bm, px + v[0] * depth * 0.62, py + v[1] * depth * 0.62,
                 z0 + shelf,
                 [(depth * 0.30, 0.0), (depth * 0.26, col_h)], 6)
    for i in range(n):                                               # 아치
        s0, s1 = step * i, step * (i + 1)
        q0 = (p0[0] + u[0] * s0 + v[0] * depth * 0.42,
              p0[1] + u[1] * s0 + v[1] * depth * 0.42)
        q1 = (p0[0] + u[0] * s1 + v[0] * depth * 0.42,
              p0[1] + u[1] * s1 + v[1] * depth * 0.42)
        zakomara(bm, q0, q1, z0 + shelf + col_h, step * 0.46,
                 -depth * 0.42, steps=steps)
    slab(0.0, L, 0.0, depth * 1.25, z0 + h * 0.92, z0 + h)           # 위 처마
    return n


def portal(bm, p_mid, u, v, z0, w, h, depth=0.55, rings=3):
    """원근 포탈(перспективный портал) — 층층이 좁아지는 아치형 출입구.

    벽에 구멍을 뚫지 않는다. **테두리를 겹쳐 놓아** 안으로 들어가는 것처럼
    보이게 한다. 구멍은 게임 스케일에서 안 보이고 삼각형만 먹는다.
    """
    for k in range(rings):
        f = 1.0 - k * 0.16
        d = depth * (k + 1) / rings
        hw, hh = w * 0.5 * f, h * f
        q0 = (p_mid[0] - u[0] * hw + v[0] * d, p_mid[1] - u[1] * hw + v[1] * d)
        q1 = (p_mid[0] + u[0] * hw + v[0] * d, p_mid[1] + u[1] * hw + v[1] * d)
        # 문설주 두 개
        for q in (q0, q1):
            _revolve(bm, q[0], q[1], z0,
                     [(w * 0.055, 0.0), (w * 0.050, hh * 0.62)], 6)
        # 반원 아치 머리
        zakomara(bm, q0, q1, z0 + hh * 0.62, hw * 0.92, -w * 0.10, steps=6)
    return h


def zakomara(bm, p0, p1, z0, h, depth, steps=10):
    """자코마라 — 벽 상단을 반원으로 마감한 **구조** 요소.

    p0→p1 이 한 베이의 폭이고, 볼트 반경 = 베이 폭 / 2 다.
    아르한겔스키 대성당은 이 안을 백석 가리비 껍데기로 채운다.

    **속이 찬 박공이다.** 처음에 곡면 스트립만 만들었더니 렌더에서 벽 위에
    얹힌 가느다란 테두리로만 보였다 — 자코마라는 내부 볼트 단면을 그대로
    드러낸 **벽면 그 자체**라 벽 두께만큼 채워져야 지붕선으로 읽힌다.
    반원 + 밑변으로 닫힌 볼록 다각형을 만들어 depth 만큼 밀어낸다.
    """
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    if L < 1e-6:
        return 0.0
    u = (dx / L, dy / L)
    v = (-u[1], u[0])
    # 반원 호 + 밑변. 시작·끝점이 z=0 이라 다각형이 닫힌다.
    prof = []
    for i in range(steps + 1):
        ang = math.pi * i / steps
        prof.append((L * (0.5 - 0.5 * math.cos(ang)), h * math.sin(ang)))
    rings = []
    for d in (0.0, depth):
        side = [bm.verts.new(
            (p0[0] + u[0] * s + v[0] * d, p0[1] + u[1] * s + v[1] * d, z0 + z))
            for s, z in prof]
        rings.append(side)
    a_, b_ = rings
    n = len(prof)
    if depth >= 0.0:
        bm.faces.new(list(reversed(a_)))
        bm.faces.new(b_)
    else:
        bm.faces.new(a_)
        bm.faces.new(list(reversed(b_)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a_[i], a_[j], b_[j], b_[i]))
    return h


def build_test(coll=None):
    """형태 문법 견본 한 줄. 실루엣 검증용."""
    coll = coll or hanok.new_collection("크렘린_돔_견본")
    bm = bmesh.new()
    # 양파돔 + 드럼 + 소구 + 십자가
    drum(bm, 0, 0, 0, 2.0, 5.0)
    hd = onion(bm, 0, 0, 5.0, 2.0)
    ball(bm, 0, 0, 5.0 + hd, 0.42)
    cross(bm, 0, 0, 5.0 + hd + 0.84, 3.0)
    # 텐트지붕
    tent(bm, 14, 0, 0, 3.2, 9.0, sides=8, flare=0.06)
    kokoshnik_ring(bm, 14, 0, 0.0, 3.3, 8, 1.9, 1.5)
    # 별
    star(bm, 26, 0, 6.0, 3.75)
    hanok.bm_to_object(bm, "크렘린_돔_견본", 'gold_dome', coll)
    return coll
