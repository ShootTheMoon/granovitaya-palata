# -*- coding: utf-8 -*-
"""성당광장(Соборная площадь) — 3대 성당 + 이반 대제 종탑 + 부속 건물.

크렘린 언덕의 **최고 지점**이고, 7개 성당과 3개 궁전이 둘러싼다.
광장 면적 9,820 m² 는 OSM 폴리곤 실측이다(문헌에서 못 찾았던 값).

십자형 돔 성당(крестово-купольный храм)의 형태 문법은 하나다:

    벽체 → 자코마라 → 드럼 → 양파돔 → 소구 → 십자가

각 요소의 의미가 형태를 강제한다.
  · **자코마라**는 내부 원통 볼트의 단면을 그대로 밖에 드러낸 것이다. 그래서
    베이 폭 = 자코마라 폭이고 볼트 반경 = 베이 폭 / 2 다. 장식이 아니라
    구조라서 마음대로 개수를 못 정한다 — 기둥 배열이 정한다.
  · **돔 개수**에는 상징이 있다. 5 = 그리스도 + 4복음사가(우스펜스키·
    아르한겔스키), 9 = 천사 9계급(블라고베셴스키). 임의로 못 바꾼다.
  · 돔은 **동쪽으로 치우쳐** 배치된다(сдвинуты к востоку). 제단이 동쪽이라
    그 위에 중앙 돔이 온다.
  · 앱스(반원 제단)는 **동쪽 면**에만 붙는다.

방위
    정교회 성당은 동쪽을 향한다. OSM 주축 각(yaw)이 그대로 동쪽 방향이고,
    세 성당 모두 7~16도로 정동에서 조금 틀어져 있다. 앱스를 +u(동) 쪽에 붙인다.
"""

import math

import bmesh

import hanok
from kremlin import dome, measured
from kremlin.measured import val

GROUND = 0.0

# 성당광장은 크렘린 언덕 최고 지점이다. 성벽 안 기준면보다 살짝 높다.
# ⚠ derived — 지형을 넣지 않기로 했으므로 상징적인 값이다.
SQUARE_Z = 1.6


def _uv(east_deg):
    """동쪽 단위벡터 u, 북쪽 단위벡터 v."""
    r = math.radians(east_deg)
    c, s = math.cos(r), math.sin(r)
    return (c, s), (-s, c)


def _pt(cx, cy, u, v, a, b):
    return (cx + u[0] * a + v[0] * b, cy + u[1] * a + v[1] * b)


def _box(bm, cx, cy, u, v, le, ln, z0, z1, inset=0.0):
    """동서 le, 남북 ln 인 직육면체."""
    he, hn = le / 2.0 - inset, ln / 2.0 - inset
    poly = [_pt(cx, cy, u, v, -he, -hn), _pt(cx, cy, u, v, he, -hn),
            _pt(cx, cy, u, v, he, hn), _pt(cx, cy, u, v, -he, hn)]
    a = [bm.verts.new((p[0], p[1], z0)) for p in poly]
    b = [bm.verts.new((p[0], p[1], z1)) for p in poly]
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((a[i], a[j], b[j], b[i]))
    return poly


def _apses(bm, cx, cy, u, v, le, ln, n, z0, h):
    """동쪽 면에 붙는 반원 제단. 우스펜스키·아르한겔스키 5개, 블라고베셴스키 3개."""
    step = ln / n
    r = step * 0.46
    ex = le / 2.0
    for i in range(n):
        b = -ln / 2.0 + step * (i + 0.5)
        # 가운데 앱스가 가장 크게 튀어나온다
        k = 1.0 + 0.35 * (1.0 - abs(i - (n - 1) / 2.0) / max(1.0, (n - 1) / 2.0))
        px, py = _pt(cx, cy, u, v, ex, b)
        prof = [(r * k, 0.0), (r * k, h * 0.92), (r * k * 0.72, h)]
        dome._revolve(bm, px, py, z0, prof, 12)


def _facade_zakomara(bm, cx, cy, u, v, le, ln, bays_e, bays_n, z0, rise, depth):
    """네 면에 자코마라를 두른다. 동쪽은 앱스가 있어 건너뛴다.

    **감김 방향이 관건이다.** dome.zakomara 는 p0→p1 의 왼쪽으로 depth 만큼
    민다. 박공은 건물 **안쪽**으로 채워져야 하므로 면마다 순서를 맞춰야 한다.
    처음에 남면과 북면의 부호를 뒤집어 놓아서 박공이 벽 밖으로 튀어나왔다.
    """
    n_made = 0
    # 남·북 면 (동서로 bays_e 개)
    #   남면(-v): p0→p1 을 +u 로 두면 왼쪽 법선이 +v = 안쪽
    #   북면(+v): 반대로 -u 순서여야 왼쪽 법선이 -v = 안쪽
    step = le / bays_e
    for sgn in (-1.0, 1.0):
        for i in range(bays_e):
            a0 = -le / 2.0 + step * i
            a1 = a0 + step
            p0 = _pt(cx, cy, u, v, a0, sgn * ln / 2.0)
            p1 = _pt(cx, cy, u, v, a1, sgn * ln / 2.0)
            if sgn > 0:
                p0, p1 = p1, p0
            dome.zakomara(bm, p0, p1, z0, rise, depth)
            n_made += 1
    # 서쪽 면(-u): -v 순서여야 왼쪽 법선이 +u = 안쪽.
    # 동쪽은 앱스 차지라 안 놓는다.
    step = ln / bays_n
    for i in range(bays_n):
        b0 = -ln / 2.0 + step * i
        b1 = b0 + step
        p0 = _pt(cx, cy, u, v, -le / 2.0, b0)
        p1 = _pt(cx, cy, u, v, -le / 2.0, b1)
        dome.zakomara(bm, p1, p0, z0, rise, depth)
        n_made += 1
    return n_made


def _dome_layout(n):
    """돔 n 개의 (동쪽 오프셋 계수, 북쪽 오프셋 계수, 크기 계수) 배치.

    중앙이 가장 크고 동쪽으로 치우친다. 5돔은 중앙 + 네 귀퉁이,
    9돔은 거기에 정방향 4개를 더한다(블라고베셴스키).
    """
    lay = [(0.10, 0.00, 1.00)]
    if n >= 5:
        for a in (-1, 1):
            for b in (-1, 1):
                lay.append((0.10 + a * 0.30, b * 0.30, 0.60))
    if n >= 9:
        for a, b in ((0.52, 0.0), (-0.34, 0.0), (0.10, 0.40), (0.10, -0.40)):
            lay.append((a, b, 0.46))
    return lay[:n]


def build_church(bm, bm_gold, name, spec, coll=None):
    """십자형 돔 성당 하나. (총고, 돔 수) 반환."""
    cx, cy = spec['x'], spec['y']
    east = spec['east']
    u, v = _uv(east)
    le, ln = spec['le'], spec['ln']
    z0 = GROUND + SQUARE_Z
    wall_h = spec['wall_h']
    top = spec['height_cross']
    n_dome = spec['domes']

    # 1. 기단 + 벽체
    _box(bm, cx, cy, u, v, le + 1.4, ln + 1.4, z0 - 0.9, z0 + 0.55)
    _box(bm, cx, cy, u, v, le, ln, z0, z0 + wall_h)

    # 2. 리제나(벽면을 베이로 가르는 세로 띠) — 자코마라의 기둥선을 밖에 드러낸다
    bays_e, bays_n = spec['bays_e'], spec['bays_n']
    for i in range(bays_e + 1):
        a = -le / 2.0 + le * i / bays_e
        for sgn in (-1.0, 1.0):
            p = _pt(cx, cy, u, v, a, sgn * ln / 2.0)
            _box(bm, p[0], p[1], u, v, 0.85, 0.55, z0, z0 + wall_h)
    for i in range(bays_n + 1):
        b = -ln / 2.0 + ln * i / bays_n
        p = _pt(cx, cy, u, v, -le / 2.0, b)
        _box(bm, p[0], p[1], u, v, 0.55, 0.85, z0, z0 + wall_h)

    # 2b. **아케이드 열주대** — 벽 중간을 가로로 두른다.
    #     우스펜스키에서 가장 알아보기 쉬운 요소이고, 이게 없으면 흰 상자다.
    belt_z = z0 + wall_h * 0.54
    belt_h = wall_h * 0.135
    faces = [
        (_pt(cx, cy, u, v, -le / 2, -ln / 2), _pt(cx, cy, u, v, le / 2, -ln / 2)),
        (_pt(cx, cy, u, v, le / 2, ln / 2), _pt(cx, cy, u, v, -le / 2, ln / 2)),
        (_pt(cx, cy, u, v, -le / 2, ln / 2), _pt(cx, cy, u, v, -le / 2, -ln / 2)),
    ]
    for q0, q1 in faces:
        dome.arcade_belt(bm, q0, q1, belt_z, belt_h,
                         pitch=1.35, depth=wall_h * 0.028)

    # 2c. 열주대 위 좁은 창 — 베이마다 하나. 러시아 성당 창은 슬릿에 가깝다
    win_z = belt_z + belt_h + wall_h * 0.06
    win_h = wall_h * 0.20
    for sgn, cnt in ((-1.0, bays_e), (1.0, bays_e)):
        step = le / cnt
        for i in range(cnt):
            a = -le / 2.0 + step * (i + 0.5)
            p = _pt(cx, cy, u, v, a, sgn * ln / 2.0)
            dome._slot(bm, p[0], p[1], win_z, step * 0.13, win_h,
                       wall_h * 0.020,
                       math.atan2(sgn * v[1], sgn * v[0]), arch=True)
    step = ln / bays_n
    for i in range(bays_n):
        b = -ln / 2.0 + step * (i + 0.5)
        p = _pt(cx, cy, u, v, -le / 2.0, b)
        dome._slot(bm, p[0], p[1], win_z, step * 0.13, win_h, wall_h * 0.020,
                   math.atan2(-u[1], -u[0]), arch=True)

    # 2d. 원근 포탈 — 서쪽(정문)과 남쪽
    dome.portal(bm, _pt(cx, cy, u, v, -le / 2.0, 0.0), v, (-u[0], -u[1]),
                z0, ln * 0.20, wall_h * 0.42, depth=wall_h * 0.030)
    dome.portal(bm, _pt(cx, cy, u, v, 0.0, -ln / 2.0), u, (-v[0], -v[1]),
                z0, le * 0.14, wall_h * 0.38, depth=wall_h * 0.030)

    # 3. 앱스 — 동쪽 면에만
    _apses(bm, cx, cy, u, v, le, ln, spec['apses'], z0, wall_h * 0.74)

    # 4. 자코마라 — 베이 폭이 곧 자코마라 폭이고 볼트 반경은 그 절반이다
    # 자코마라 깊이 = 벽 두께. 얇은 판이 아니라 벽면이 반원으로 올라간 것이다.
    rise_e = (le / bays_e) * 0.5
    _facade_zakomara(bm, cx, cy, u, v, le, ln, bays_e, bays_n,
                     z0 + wall_h, rise_e, 1.5)

    # 5. 드럼 + 양파돔. 총고에서 역산해 드럼 높이를 정한다
    # 정점이 공표 총고에 정확히 닿게 드럼 높이를 **역산**한다.
    #   정점 = z_drum + drum_h + dome_h + (소구 오프셋 r_c*0.40) + cross_h
    # 처음에 역산식과 반환식의 오프셋이 어긋나 우스펜스키가 46.8 m 로 나왔다
    # (공표 49 m 대비 -4.5%). 두 식에 같은 상수를 쓴다.
    BALL_OFF = 0.40
    # 돔이 많을수록 중앙 돔이 작아진다 — 9돔인 블라고베셴스키에 5돔과 같은
    # 크기를 주면 지붕으로 꽉 차 버린다.
    r_c = ln * 0.155 * (5.0 / max(5.0, n_dome)) ** 0.35
    shape = spec.get('dome_shape', 'onion')
    d_ratio = (dome.HELMET_H_RATIO if shape == 'helmet'
               else val(measured.DOME, 'height_ratio'))
    dome_h_c = 2.0 * r_c * d_ratio
    cross_h = top * 0.062
    z_drum = z0 + wall_h + rise_e * 0.55
    drum_raw = top + GROUND - z_drum - dome_h_c - cross_h - r_c * BALL_OFF
    drum_h = max(2.0, drum_raw)
    # **클램프를 조용히 넘기지 않는다.** drum_raw 가 음수라는 것은 주어진
    # 총고가 벽체 높이 + 돔 크기와 기하적으로 양립하지 않는다는 뜻이다.
    # 실제로 아르한겔스키(추정 40 m)와 블라고베셴스키(추정 32 m)에서 그렇게
    # 나왔고, 그 덕에 추정치가 틀렸다는 것을 알았다.
    spec['_clamped'] = (drum_raw < 2.0)
    spec['_drum_raw'] = drum_raw

    n_made = 0
    for fa, fb, fs in _dome_layout(n_dome):
        px, py = _pt(cx, cy, u, v, le * fa, ln * fb)
        r = r_c * fs
        dh = drum_h * (1.0 if fs > 0.9 else 0.72)
        # 드럼에 창을 낸다. 드럼은 채광이 목적이라 창 없는 드럼은 굴뚝이다.
        dome.drum(bm, px, py, z_drum, r, dh, seg=16,
                  windows=(12 if fs > 0.9 else 8), arcade=True)
        # 드럼 기부 코코시닉 — 17세기 이전 성당에는 없지만 크렘린 3대 성당은
        # 후대 개보수에서 다 붙었다
        dome.kokoshnik_ring(bm, px, py, z_drum, r * 1.02, 8,
                            r * 0.62, dh * 0.22, depth=r * 0.10)
        hd = dome.onion(bm_gold, px, py, z_drum + dh, r,
                        seg=20 if fs > 0.9 else 14,
                        steps=22 if fs > 0.9 else 14, shape=shape)
        dome.ball(bm_gold, px, py, z_drum + dh + hd, r * 0.20, 10)
        dome.cross(bm_gold, px, py, z_drum + dh + hd + r * BALL_OFF,
                   cross_h * (1.0 if fs > 0.9 else 0.78), yaw=math.radians(east))
        n_made += 1
    apex = z_drum + drum_h + dome_h_c + r_c * BALL_OFF + cross_h
    return apex, n_made


# ---------------------------------------------------------------- 제원

def _spec():
    U, A, B = measured.USPENSKY, measured.ARKHANGELSKY, measured.BLAGOVESHCHENSKY
    return {
        '우스펜스키': dict(
            x=val(U, 'x'), y=val(U, 'y'), east=val(U, 'yaw'),
            le=val(U, 'length'), ln=val(U, 'width'),
            wall_h=val(U, 'height_wall'), height_cross=val(U, 'height_cross'),
            domes=val(U, 'domes'), apses=5,
            # 1479년 건물이라 **투구형**이다. 양파돔은 17세기 이후 형식이다.
            dome_shape='helmet',
            # 내부를 동일 크기 정사각형 12개로 나눈다 → 4 × 3
            bays_e=4, bays_n=3),
        '아르한겔스키': dict(
            x=val(A, 'x'), y=val(A, 'y'), east=val(A, 'yaw'),
            le=val(A, 'length'), ln=val(A, 'width'),
            wall_h=val(A, 'height_wall'), height_cross=val(A, 'height_cross'),
            domes=val(A, 'domes'), apses=5,
            dome_shape='helmet',        # 1508년. 우스펜스키와 같은 시기
            bays_e=4, bays_n=3),
        '블라고베셴스키': dict(
            x=val(B, 'x'), y=val(B, 'y'), east=val(B, 'yaw'),
            le=val(B, 'length'), ln=val(B, 'width'),
            wall_h=val(B, 'height_wall'), height_cross=val(B, 'height_cross'),
            # 9돔 = 천사 9계급. 4기둥·3앱스라 베이가 하나 적다
            domes=val(B, 'domes'), apses=3,
            bays_e=3, bays_n=3),
    }


def build_bell_tower(bm, bm_gold, coll):
    """이반 대제 종탑 — 팔각 3단 + 원통 드럼 + 금박 양파돔. 81 m.

    원형도 0.81 이 팔각형을 가리킨다(정사각 0.785, 원 1.0). 문헌의
    «три восьмерика» 서술과 OSM 지오메트리가 일치한다.
    """
    I = measured.IVAN_BELL
    x, y = val(I, 'x'), val(I, 'y')
    yaw = math.radians(val(I, 'yaw'))
    H = val(I, 'height')
    r0 = 0.5 * (val(I, 'width') + val(I, 'depth')) / 2.0
    z = GROUND + SQUARE_Z

    # 팔각 3단. 위로 갈수록 좁아진다.
    #
    # **1단은 속이 찬 석조, 2·3단은 뚫린 종루다.**
    # 처음에 3단 전부 통짜 팔각기둥으로 세우고 벽에 파인 박스를 붙여 개구부를
    # 흉내 냈더니, (a) 테이퍼를 무시한 반경에 놓아 벽 밖으로 튀어나온
    # 지느러미가 됐고 (b) 애초에 **더하기 박스로는 관통 개구부가 안 된다**
    # (불리언은 금지). 종루는 실제로 기둥 사이가 뚫린 구조이므로
    # **기둥 8개 + 그 사이 아치**로 짓는다. 34개 종이 여기 걸린다.
    r = r0
    tier_h = [H * 0.30, H * 0.22, H * 0.16]
    for i, hh in enumerate(tier_h):
        rt = r * 0.90
        verts_at = lambda rad: [
            (x + rad * math.cos(yaw + math.pi / 8 + math.pi * k / 4),
             y + rad * math.sin(yaw + math.pi / 8 + math.pi * k / 4))
            for k in range(8)]
        lo, hi = verts_at(r), verts_at(rt)

        if i == 0:
            # 속이 찬 석조 1단
            a = [bm.verts.new((p[0], p[1], z)) for p in lo]
            b = [bm.verts.new((p[0], p[1], z + hh)) for p in hi]
            bm.faces.new(list(reversed(a)))
            for k in range(8):
                j = (k + 1) % 8
                bm.faces.new((a[k], a[j], b[j], b[k]))
            # 좁은 창. 테이퍼를 반영해 **그 높이의 실제 반경**에 놓는다.
            for k in range(8):
                fa = yaw + math.pi / 4.0 + math.pi * k / 4.0
                rm = r + (rt - r) * 0.5
                ap = rm * math.cos(math.pi / 8.0)
                dome._slot(bm, x + ap * math.cos(fa), y + ap * math.sin(fa),
                           z + hh * 0.34, r * 0.16, hh * 0.34, r * 0.10,
                           fa, arch=True)
        else:
            # 뚫린 종루 — 바닥 슬래브 + 기둥 8 + 그 사이 아치
            base = [bm.verts.new((p[0], p[1], z)) for p in lo]
            base_t = [bm.verts.new((p[0], p[1], z + hh * 0.09)) for p in lo]
            bm.faces.new(list(reversed(base)))
            bm.faces.new(base_t)
            for k in range(8):
                j = (k + 1) % 8
                bm.faces.new((base[k], base[j], base_t[j], base_t[k]))
            pier = r * 0.30           # 가늘면 앙상해 보인다. 0.20 은 부족했다
            z_p = z + hh * 0.09
            for k in range(8):
                px, py = lo[k]
                dome._revolve(bm, px, py, z_p,
                              [(pier, 0.0), (pier * 0.92, hh * 0.58)], 6)
            # 기둥 사이 반원 아치.
            # **아치를 기둥 선에 걸치게 한다.** 꼭짓점을 그대로 쓰고 안쪽으로만
            # 밀면 아치가 기둥 열 바깥에 뜬 띠처럼 보인다 — 실제로 그랬다.
            # 바깥으로 pier 만큼 밀어 놓고 두께를 2·pier 로 줘서 기둥을 감싼다.
            for k in range(8):
                j = (k + 1) % 8
                q0, q1 = lo[k], lo[j]
                ex, ey = q1[0] - q0[0], q1[1] - q0[1]
                chord = math.hypot(ex, ey)
                if chord < 1e-6:
                    continue
                # q0→q1 의 왼쪽 법선이 안쪽이므로 오른쪽이 바깥이다
                ox, oy = ey / chord, -ex / chord
                s0 = (q0[0] + ox * pier * 0.95, q0[1] + oy * pier * 0.95)
                s1 = (q1[0] + ox * pier * 0.95, q1[1] + oy * pier * 0.95)
                dome.zakomara(bm, s0, s1, z_p + hh * 0.58,
                              chord * 0.42, pier * 1.9, steps=6)
            # 아치 위 처마
            top_r = rt * 1.04
            tv = verts_at(top_r)
            c0 = [bm.verts.new((p[0], p[1], z + hh * 0.80)) for p in tv]
            c1 = [bm.verts.new((p[0], p[1], z + hh)) for p in tv]
            bm.faces.new(list(reversed(c0)))
            bm.faces.new(c1)
            for k in range(8):
                j = (k + 1) % 8
                bm.faces.new((c0[k], c0[j], c1[j], c1[k]))

        dome.kokoshnik_ring(bm, x, y, z + hh, rt * 1.02, 8,
                            rt * 0.55, hh * 0.16, depth=rt * 0.10,
                            phase=yaw + math.pi / 8)
        z += hh
        r = rt * 0.86

    # 원통 드럼(1600년 증축분) + 금박 양파돔 + 십자가.
    # 성당과 같은 이유로 드럼 높이를 **총고 81 m 에서 역산**한다.
    rd = r * 0.92
    hd = 2.0 * rd * val(measured.DOME, 'height_ratio')
    cross_h = H * 0.055
    drum_h = max(2.0, H + GROUND - z - hd - cross_h - rd * 0.40)
    dome.drum(bm, x, y, z, rd, drum_h, seg=18)
    z += drum_h
    dome.onion(bm_gold, x, y, z, rd, height=hd, seg=22)
    dome.ball(bm_gold, x, y, z + hd, rd * 0.20, 10)
    dome.cross(bm_gold, x, y, z + hd + rd * 0.40, cross_h, yaw=yaw)
    return z + hd + rd * 0.40 + cross_h


def build_plain(bm, name, row, z_top_frac=1.0):
    """부속 건물 — 상자 압출. 형태를 모르는 것은 지어내지 않는다."""
    rel, x, y, w, d, yaw, h, conf = row
    u, v = _uv(yaw)
    _box(bm, x, y, u, v, w, d, GROUND + SQUARE_Z - 0.5,
         GROUND + SQUARE_Z + h * z_top_frac)
    return h


def build(coll=None):
    coll = coll or hanok.new_collection("크렘린_성당")
    coll_b = hanok.new_collection("크렘린_종탑")
    bm = bmesh.new()
    bm_gold = bmesh.new()
    bm_b = bmesh.new()
    bm_bg = bmesh.new()
    st = {'churches': 0, 'domes': 0, 'tops': {}, 'err': [], 'clamped': []}

    for name, spec in _spec().items():
        try:
            top, nd = build_church(bm, bm_gold, name, spec)
        except Exception as exc:                     # noqa: BLE001
            st['err'].append((name, repr(exc)))
            continue
        st['churches'] += 1
        st['domes'] += nd
        st['tops'][name] = round(top, 1)
        if spec.get('_clamped'):
            st['clamped'].append(
                "%s: 드럼 높이가 %.1f m (음수/과소) 로 나와 2.0 m 로 클램프됨 — "
                "총고 %.0f m 추정치가 벽체 %.0f m + 돔과 양립하지 않는다"
                % (name, spec['_drum_raw'], spec['height_cross'], spec['wall_h']))

    try:
        st['tops']['이반대제 종탑'] = round(build_bell_tower(bm_b, bm_bg, coll_b), 1)
    except Exception as exc:                         # noqa: BLE001
        st['err'].append(('이반대제 종탑', repr(exc)))

    # 부속 건물은 형태 자료가 없어 상자로만 둔다
    for name, row in measured.SQUARE_BUILDINGS.items():
        build_plain(bm, name, row)

    hanok.bm_to_object(bm, "크렘린_성당_석조", 'whitewash', coll)
    hanok.bm_to_object(bm_gold, "크렘린_성당_금박돔", 'gold_dome', coll)
    hanok.bm_to_object(bm_b, "크렘린_종탑_석조", 'whitewash', coll_b)
    hanok.bm_to_object(bm_bg, "크렘린_종탑_금박돔", 'gold_dome', coll_b)
    return coll, st
