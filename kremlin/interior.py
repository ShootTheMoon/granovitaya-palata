# -*- coding: utf-8 -*-
"""파세트궁 실내 — 외부를 버리고 방 하나만 짓는다.

`granovitaya.py` 는 **사이트에 선 건물**이다: OSM 발자국에서 중심과 yaw 14° 를
받아 오고, подклет 위에 홀을 얹고, 러스티케이션 외피와 지붕을 두른다.

이 모듈은 같은 치수로 **방만** 짓는다. 바뀌는 것은 셋뿐이다.

  1. **원점 축정렬** — cx = cy = yaw = 0. `Site.w()` 가 항등이 된다.
     이게 이 모듈이 존재하는 진짜 이유다. `export_overdare.extract_boxes()` 는
     `matrix_world` 를 구운 **월드 좌표**에서 축정렬 박스를 찾으므로, yaw 14°
     에서는 바닥·기둥·다도가 절대 네이티브 Part 가 못 된다. 축을 맞추면
     그것들이 **이미 순수 박스**라서 손대지 않고 Part 로 나간다.
  2. **подклет 제거** — floor = 0. 그래서 모든 레벨이 `podklet_h` 만큼 내려온다.
     `measured` 의 `window_sill`·`window_head`·`vault_*` 는 원래부터 「홀 바닥
     기준」 값이라 그대로 쓰면 되고, `wall_top`·`cornice_top` 만 지면 기준이라
     빼 준다.
  3. **위를 닫는다** — 지붕을 버렸으니 벽 위가 하늘로 열린다. 평평한 캡을 씌운다.
     안에서는 볼트에 가려 안 보이지만, 없으면 지붕 공간으로 빛이 샌다.

치수는 전부 `measured.GRANOVITAYA` 에서 읽는다. **새 상수를 만들지 않는다.**
벽·창·볼트·다도를 만드는 함수도 `granovitaya` 것을 그대로 부른다 — 복제하면
Табл.12~15 실측을 두 곳에서 관리하게 된다.
"""

import math

import bmesh
import bpy
from mathutils import Vector

import hanok
from kremlin import granovitaya, measured, vault
from kremlin.measured import val

# 컬렉션 이름은 **사이트 전역에서 유일**해야 한다 — `sites._check()` 가 중복을
# import 시점에 터뜨린다. 그냥 「실내_」로 두면 나중에 다른 궁궐 실내와 부딪히므로
# 건물 이름을 붙인다.
COLL = {
    'wall':     "파세트실내_벽체",
    'vault':    "파세트실내_볼트",
    'pier':     "파세트실내_기둥",
    'floor':    "파세트실내_바닥",
    'dado':     "파세트실내_다도",
    'cap':      "파세트실내_천장캡",
    'grille':   "파세트실내_창살",
    'impost':   "파세트실내_임포스트",
    'collider': "파세트실내_콜라이더",
    'prop':     "파세트실내_소품",
    # 아랫층(подклет) — 전부 축정렬 박스라 통째로 네이티브 Part 다
    'p_wall':   "파세트실내_하층벽",
    'p_floor':  "파세트실내_하층바닥",
    'p_pier':   "파세트실내_하층기둥",
    'stair':    "파세트실내_계단",
}

CAP_T = 0.40          # 천장 캡 두께

# 순수 축정렬 박스로만 지어 **네이티브 Part 로 나갈** 부재들.
# `sites.KRM_INTERIOR['part_groups']` 와 짝이 맞아야 한다.
PART_KEYS = {'floor', 'pier', 'dado', 'cap', 'impost', 'collider',
             'p_wall', 'p_floor', 'p_pier', 'stair'}


class Site(granovitaya.Site):
    """`granovitaya.Site` 와 같은 치수, 다른 좌표계.

    부모의 `__init__` 을 부르지 않는다 — 그쪽은 첫 줄에서 `footprint()` 로
    OSM 을 읽는데 실내에는 발자국이 필요 없다. 대신 필드를 전부 여기서 채운다.
    `w()` · `box()` 는 부모 것을 그대로 쓴다 (yaw 0 이라 `w()` 는 항등).
    """

    def __init__(self):
        g = measured.GRANOVITAYA

        self.cx, self.cy, self.yaw = 0.0, 0.0, 0.0
        self._c, self._s = 1.0, 0.0
        self.ext_u = self.ext_v = 0.0          # 발자국을 안 쓴다

        self.hall = val(g, 'hall_inner')
        self.pier_side = val(g, 'pier_side')
        self.w_east = val(g, 'wall_east')
        self.w_north = val(g, 'wall_north')
        self.w_south = val(g, 'wall_south')
        self.w_seni = val(g, 'wall_seni')
        self.seni = val(g, 'seni_depth')
        self.seni_o = val(g, 'seni_outer')

        self.lu = self.seni_o + self.seni + self.w_seni + self.hall + self.w_east
        self.lv = self.w_north + self.hall + self.w_south

        # подклет 을 들어냈다. 홀 바닥이 z = 0 이다.
        podklet = val(g, 'podklet_h')
        self.floor = 0.0
        self.spring = val(g, 'vault_spring_h')
        self.crown = val(g, 'vault_h')
        self.sill = val(g, 'window_sill')
        self.head = val(g, 'window_head')
        # 지면 기준 값이라 подклет 만큼 내린다. 15.7 - 3.0 = 12.7.
        self.wall_top = val(g, 'wall_top') - podklet
        self.cornice = val(g, 'cornice_top') - podklet
        # 지붕이 없다. 부모 코드가 `apex` 를 읽을 수 있으므로 벽 상단에 맞춰 둔다.
        self.apex = self.wall_top

        self.hu0 = -self.lu / 2.0 + self.seni_o + self.seni + self.w_seni
        self.hu1 = self.hu0 + self.hall
        self.hv0 = -self.lv / 2.0 + self.w_north
        self.hv1 = self.hv0 + self.hall
        self.hcu = (self.hu0 + self.hu1) / 2.0
        self.hcv = (self.hv0 + self.hv1) / 2.0

        # ⚠ 원점은 **블록 중심**이지 홀 중심이 아니다.
        #   홀 중심으로 옮기려다 말았다 — `granovitaya.build_shell()` 이
        #   `u0, u1 = -site.lu/2, site.lu/2` 를 **직접** 계산하기 때문에,
        #   필드만 밀면 벽은 안 밀린 자리에 서고 창·다도만 밀려서 방이 어긋난다.
        #   축정렬이기만 하면 `extract_boxes()` 는 통과하므로 원점이 어디든
        #   상관없다. сени 가 서쪽에 붙어 있어 홀 중심은 u ≈ +3.4 에 온다.
        #   소품 배치는 `hcu`·`hcv` 를 읽으면 되고 상수를 손으로 적을 일이 없다.

    # --- 블록 경계. 부모가 직접 계산하는 값과 같은 것을 이름으로 노출한다.
    @property
    def u0(self):
        return -self.lu / 2.0

    @property
    def u1(self):
        return self.lu / 2.0

    @property
    def v0(self):
        return -self.lv / 2.0

    @property
    def v1(self):
        return self.lv / 2.0


# ------------------------------------------------------------------ 새 부재


def portal_rect(site, bay=0):
    """сени 격벽에 낼 개구부 (v_a, v_b, z_a, z_b).

    **베이 중앙에 놓는다.** 홀 서벽의 루넷은 베이 경계에서 스프링잉(3.4)까지
    내려오므로, 전고 2.75 짜리 개구부라도 경계에 두면 그 위 인방·조각 틀이
    볼트에 물린다. 베이 중앙에서는 루넷이 9.0 까지 올라가 여유가 크다.
    `measured.GRANOVITAYA['portal_at_bay_centre']` 에 근거를 적어 뒀다.

    ⚠ 두 베이 중 어느 쪽인지는 **미확정**이다 — Табл.12 평면에 포털 표시가
      없다. `bay=0` 이 v 가 작은 쪽이다.
    """
    g = measured.GRANOVITAYA
    w = val(g, 'portal_open_w')
    h = val(g, 'portal_open_h')
    half_bay = site.hall / 4.0
    vc = site.hv0 + half_bay + (site.hall / 2.0) * bay
    return (vc - w / 2.0, vc + w / 2.0, 0.0, h)


def build_impost(site, bm, h=0.35, out=0.14):
    """볼트가 앉는 높이를 도는 **임포스트 띠**(주두 층).

    벽이 바닥부터 볼트까지 민면이라 눈이 붙을 데가 없었다. 스프링잉(3.4)에
    띠를 하나 두르면 벽이 「다도 - 민면 - 임포스트 - 루넷」으로 읽힌다.
    중앙 기둥에는 이미 주두가 있으므로(`vault.pier` 의 cap) **같은 높이**에
    두어 선이 이어지게 한다.

    창(문턱 4.1)보다 아래, 포털(머리 2.75)보다 위라 어느 개구부와도 안 겹친다.
    상자 4개 → 네이티브 Part.
    """
    z0, z1 = site.spring - h * 0.5, site.spring + h * 0.5
    a0, a1, b0, b1 = site.hu0, site.hu1, site.hv0, site.hv1
    site.box(bm, a0, a1, b0, b0 + out, z0, z1)
    site.box(bm, a0, a1, b1 - out, b1, z0, z1)
    site.box(bm, a0, a0 + out, b0 + out, b1 - out, z0, z1)
    site.box(bm, a1 - out, a1, b0 + out, b1 - out, z0, z1)


def _prism(site, bm, along_u, f0, f1, poly):
    """(t, z) 평면 다각형을 벽 두께 방향으로 밀어 낸 기둥.

    `Site.box()` 는 축정렬만 되므로 사선 부재(창살)를 못 만든다. 감기는
    `granovitaya._hex()` 와 같은 방식으로 **자기 중심 기준** 바깥을 향하게
    돌린다 — 손으로 맞추면 좌우 대칭에서 부호가 갈려 일부가 뒤집힌다.
    """
    def V(t, z, f):
        xy = site.w(t, f) if along_u else site.w(f, t)
        return bm.verts.new((xy[0], xy[1], z))

    a = [V(t, z, f0) for t, z in poly]
    b = [V(t, z, f1) for t, z in poly]
    n = len(poly)
    ctr = Vector((0.0, 0.0, 0.0))
    for v in a + b:
        ctr += v.co
    ctr /= float(len(a) + len(b))
    loops = [a, b[::-1]] + [[a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]]
                            for i in range(n)]
    for loop in loops:
        try:
            f = bm.faces.new(loop)
        except ValueError:
            continue
        f.normal_update()
        if f.normal.dot(f.calc_center_median() - ctr) < 0.0:
            f.normal_flip()


def _grille(site, bm, along_u, f_out, ta, tb, zs, zh, splay,
            pitch=0.30, bar=0.035, depth=0.05):
    """창 바깥쪽 개구부에 **사선 격자** 창살.

    Табл.14 대홀 사진에서 창이 사선 격자로 나뉘어 보인다. 실내에서 창은
    눈높이 위에 있지만 개구부가 크고 밝아 격자가 실루엣으로 읽힌다 —
    없으면 창이 그냥 뚫린 구멍이 된다.

    격자는 **아치 스프링잉 아래 사각 구간**에만 넣는다. 아치머리까지 정확히
    잘라 넣으려면 원호 클리핑이 필요한데, 얻는 것에 비해 면수가 비싸다.

    ⚠ 반복 요소다. Hunyuan3D 로는 못 뽑는다 — 네거티브 `重复` 와 정면충돌.
    """
    c = (ta + tb) / 2.0
    hi = (tb - ta) / 2.0
    ho = max(0.15, hi - splay)              # 바깥쪽은 사면만큼 좁다
    z1 = zh - ho                            # 바깥면 아치 스프링잉
    if z1 - zs < 2.0 * pitch:
        return
    t0, t1 = c - ho, c + ho
    # f_out 은 벽 바깥면. 창살은 거기서 안쪽으로 depth 만큼 들어간다.
    lo, hi_f = f_out - depth, f_out

    h = bar / 2.0
    for sgn in (+1, -1):
        # t - sgn*z = k 인 선들. 사각형을 넉넉히 덮도록 k 범위를 잡는다.
        k0 = t0 - sgn * (z1 if sgn > 0 else zs)
        k1 = t1 - sgn * (zs if sgn > 0 else z1)
        lo_k, hi_k = min(k0, k1), max(k0, k1)
        n = int((hi_k - lo_k) / (pitch * math.sqrt(2.0))) + 1
        for i in range(n + 1):
            k = lo_k + (hi_k - lo_k) * i / max(1, n)
            # 선분 t = k + sgn*z 를 사각형 [t0,t1]×[zs,z1] 에 클립한다.
            def t_at(z, _k=k, _s=sgn):
                return _k + _s * z
            zz = []
            for z in (zs, z1):
                if t0 <= t_at(z) <= t1:
                    zz.append(z)
            for t_e in (t0, t1):
                z = (t_e - k) / sgn
                if zs <= z <= z1:
                    zz.append(z)
            if len(zz) < 2:
                continue
            za, zb = min(zz), max(zz)
            if zb - za < 0.12:
                continue
            # 선에 수직인 오프셋 (t, z) 평면에서 45°
            d = h * math.sqrt(2.0)
            poly = [(t_at(za) - d, za), (t_at(za) + d, za),
                    (t_at(zb) + d, zb), (t_at(zb) - d, zb)]
            _prism(site, bm, along_u, lo, hi_f, poly)


def build_grilles(site, bm):
    """창 8짝 전부에 창살."""
    sp = val(measured.GRANOVITAYA, 'window_splay')
    win_e = granovitaya._clip(
        site, granovitaya._windows(site.hv0, site.hv1, 4, 1.9, site.sill, site.head),
        site.hv0)
    win_s = granovitaya._clip(
        site, granovitaya._windows(site.hu0, site.hu1, 4, 1.9, site.sill, site.head),
        site.hu0)
    for ta, tb, zs, zh in win_e:
        _grille(site, bm, False, site.u1, ta, tb, zs, zh, sp)
    for ta, tb, zs, zh in win_s:
        _grille(site, bm, True, site.v1, ta, tb, zs, zh, sp)


def build_seni_ribs(site, bm, z0=2.6, seg=20, width=0.35, out=0.16):
    """сени 원통볼트 밑에 두르는 **횡단 아치 리브**.

    Табл.13 은 сени 를 「장식 띠를 두른 횡단 아치가 반복되는」 볼트 갤러리로
    보여 준다. 작업로그 기록대로 교차볼트로 재현하려다 칸 경계마다 위가
    뚫려서 **경계 없는 원통 하나**로 갔고, 「횡단 아치는 나중에 리브로
    얹는다」고 남겨 둔 것이 이것이다.

    리브는 원통 **안쪽으로** `out` 만큼 내밀어 그림자선을 만든다.
    피치는 5.6 m — сени 안목 22.4 를 넷으로 나눈 값이고, 원래 교차볼트
    베이를 잡으려던 그 간격이다.
    """
    su0 = site.u0 + site.seni_o
    su1 = site.hu0 - site.w_seni
    span = site.seni + 0.12                    # barrel() 에 넘긴 것과 같은 값
    r = span / 2.0
    cu = (su0 + su1) / 2.0

    pitch = site.hall / 4.0
    vs = [site.hv0 + pitch * k for k in range(5)]
    vs[0] += width / 2.0                        # 끝 리브는 벽에 파묻히지 않게
    vs[-1] -= width / 2.0

    for vc in vs:
        va, vb = vc - width / 2.0, vc + width / 2.0
        prev = None
        for i in range(seg + 1):
            a = math.pi * i / seg
            u = cu - r * math.cos(a)
            z = z0 + r * math.sin(a)
            ui = cu - (r - out) * math.cos(a)
            zi = z0 + (r - out) * math.sin(a)
            cur = ((u, z), (ui, zi))
            if prev is not None:
                (pu, pz), (pui, pzi) = prev
                poly = [(pu, pz), (u, z), (ui, zi), (pui, pzi)]
                # ⚠ along_u=True 다. 리브 아치가 도는 축(t)이 **u**(원통 span)
                #   이고 두께가 v 다. False 로 두면 둘이 뒤바뀌어 리브가 сени
                #   밖으로 눕는다 — 볼트 y 범위가 -11.55 에서 -15.46 으로
                #   늘어난 것으로 잡았다.
                _prism(site, bm, True, va, vb, poly)
            prev = cur


def build_cap(site, bm):
    """벽 위를 덮는 평평한 캡.

    지붕을 버려서 생긴 부재다. 볼트(마루 9.0)와 벽 상단(12.7) 사이의 지붕
    공간은 그대로 두고 **뚜껑만** 덮는다 — 볼트를 낮추면 Табл.12 단면과
    어긋나고, 벽을 볼트에 맞춰 자르면 창 위 벽면이 사라진다.

    안에서는 볼트에 가려 안 보인다. 없으면 지붕 공간이 하늘로 열려서
    창 너머·볼트 등에서 빛이 샌다.
    """
    site.box(bm, site.u0, site.u1, site.v0, site.v1,
             site.wall_top, site.wall_top + CAP_T)


# ------------------------------------------------------------------ 아랫층


class Podklet(object):
    """подклет — 홀 바로 밑 통층. 레벨과 격자를 한 곳에서 계산한다.

    ⚠ **Табл.12 에 하층 평면이 없다.** 그래서 여기 있는 것은 전부 `derived` 다.
      다만 지어낸 정도는 세 가지로 갈린다:

      · 외벽 위치·두께 — 위층과 같다. 벽이 위에서 아래로 이어진다는 것뿐이라
        추론이라기보다 사실에 가깝다.
      · 층고 — `podklet_h` 3.0 (Табл.12 입면 실측)에서 바닥 슬래브를 뺀
        **유효 2.65 m**. 이건 계산이다.
      · 기둥 격자 — **여기가 지어낸 부분이다.** 근거는 기하 하나: 22.4 m 를
        건너지르는 볼트는 마루가 11.2 m 로 올라가야 하고, 3.0 m 층고에서는
        어떤 베이 크기로도 스프링잉이 사람 키 밑으로 내려온다. 즉 **이 층고에
        볼트는 물리적으로 불가능하다** → 기둥 격자 + 평천장이 유일한 답이다.

    격벽(w_seni)은 **안 내린다.** 내리면 아랫층도 5.1 m 복도 + 22.4 m 방으로
    갈라져 위층과 똑같이 답답하다. 대신 격벽 밑에 기둥 열을 세워 받친다 —
    그래서 아랫층은 **30.0 × 22.4 m 한 칸**이다.
    """

    SLAB = 0.35          # 바닥 슬래브 두께 (위층 바닥과 같은 값)
    PIER = 1.20          # 기둥 한 변
    STEP_RISE = 3.0 / 18.0
    STEP_GOING = 0.30

    def __init__(self, site):
        self.site = site
        self.floor = -val(measured.GRANOVITAYA, 'podklet_h')     # -3.0
        self.ceil = site.floor - self.SLAB                       # -0.35
        # ⚠ 벽은 천장(-0.35)이 아니라 **위층 바닥 레벨(0)까지** 올린다.
        #   바닥 슬래브는 벽 **안쪽면에서** 끝나므로, 벽을 천장에서 끊으면
        #   z ∈ (-0.35, 0) 인 35 cm 띠가 **사방으로 비어 있는 채로 남는다.**
        #   ray_cast 가 아랫층·сени 양쪽에서 이 틈으로 빠져나가는 것으로 잡았다.
        self.wall_top = site.floor                               # 0.0
        self.u0 = site.u0 + site.seni_o                          # 서 외벽 안쪽
        self.u1 = site.hu1                                       # 동 외벽 안쪽
        self.v0, self.v1 = site.hv0, site.hv1

        # 계단 — сени 폭 전체를 쓰는 곧은 한 단. 남쪽 끝에서 내려간다.
        self.n_step = 18
        self.run = self.n_step * self.STEP_GOING                 # 5.4
        self.su0 = site.u0 + site.seni_o
        self.su1 = site.hu0 - site.w_seni
        self.stair_v0 = self.v0
        self.stair_v1 = self.v0 + self.run

        # 기둥 격자. u 5열 × v 4행에서 계단실에 걸리는 것을 뺀다.
        du = (self.u1 - self.u0) / 6.0
        dv = (self.v1 - self.v0) / 5.0
        self.piers = []
        for i in range(1, 6):
            cu = self.u0 + du * i
            for j in range(1, 5):
                cv = self.v0 + dv * j
                if (self.su0 - self.PIER <= cu <= self.su1 + self.PIER and
                        self.stair_v0 - self.PIER <= cv <= self.stair_v1 + self.PIER):
                    continue                      # 계단실 안이다
                self.piers.append((cu, cv))

    def clear_h(self):
        return self.ceil - self.floor


def build_podklet(pod, bm_wall, bm_floor, bm_pier, bm_stair):
    """아랫층 — 외벽 · 바닥 · 기둥 · 계단. **전부 축정렬 박스다.**

    그래서 네 덩어리가 통째로 네이티브 Part 로 나간다. 메시 유닛 삼각형
    예산(파일당 30,000)을 한 개도 안 쓰고 방이 하나 늘어난다.
    """
    s = pod.site
    z0, z1 = pod.floor, pod.ceil

    # 바닥
    s.box(bm_floor, pod.u0, pod.u1, pod.v0, pod.v1, z0 - Podklet.SLAB, z0)

    # 외벽 — 위층 벽을 그대로 내린다. 창은 없다(Табл.12 입면의 подклет 구간에
    # 개구부가 안 보인다). 그래서 이 층은 자연광이 계단실로만 들어온다.
    zw = pod.wall_top
    s.box(bm_wall, s.u0, pod.u0, pod.v0, pod.v1, z0, zw)          # 서
    s.box(bm_wall, pod.u1, s.u1, pod.v0, pod.v1, z0, zw)          # 동
    s.box(bm_wall, s.u0, s.u1, s.v0, pod.v0, z0, zw)              # 북
    s.box(bm_wall, s.u0, s.u1, pod.v1, s.v1, z0, zw)              # 남

    # 기둥
    h = Podklet.PIER / 2.0
    for cu, cv in pod.piers:
        s.box(bm_pier, cu - h, cu + h, cv - h, cv + h, z0, z1)

    # 계단 — 단마다 상자 하나. 위에서 세어 내려간다.
    # ⚠ 아래에서 세면 마지막 단이 높이 0 이 되어 `Site.box()` 가 조용히 버린다.
    for j in range(1, pod.n_step):
        top = -j * Podklet.STEP_RISE
        va = pod.stair_v1 - Podklet.STEP_GOING * j
        vb = va + Podklet.STEP_GOING
        s.box(bm_stair, pod.su0, pod.su1, va, vb, z0, top)


def build_collider(site, bm, portal=None):
    """플레이어 충돌용 통짜 박스.

    오버데어 MeshPart 에는 `CollisionFidelity` 가 없고 엔진 convex 분해가
    엉성해서 **플레이어가 벽을 뚫고 나간다.** 창·아치가 있는 실제 벽체는
    축정렬 박스가 아니라 `extract_boxes()` 를 못 통과하므로, 개구부 없는
    통짜 박스를 따로 깔아 Part 로 내보낸다. 렌더에서는 숨긴다.

    지형과 달리 실내는 전부 축정렬 평면이라 **쿼드트리가 필요 없다** —
    박스 여섯 개면 끝난다.
    """
    zt = site.wall_top
    # 북·남 벽 (장변 전체를 덮는다)
    site.box(bm, site.u0, site.u1, site.v0, site.hv0, 0.0, zt)
    site.box(bm, site.u0, site.u1, site.hv1, site.v1, 0.0, zt)
    # 동 벽 · сени 외벽(서)
    site.box(bm, site.hu1, site.u1, site.hv0, site.hv1, 0.0, zt)
    site.box(bm, site.u0, site.u0 + site.seni_o, site.hv0, site.hv1, 0.0, zt)
    # сени 격벽 — 포털 자리를 비운다. 안 비우면 플레이어가 сени 에서 홀로
    # 못 넘어간다(보이는 문은 있는데 막힌 벽이 된다).
    pu0, pu1 = site.hu0 - site.w_seni, site.hu0
    if portal is None:
        site.box(bm, pu0, pu1, site.hv0, site.hv1, 0.0, zt)
    else:
        va, vb, _, ph = portal
        site.box(bm, pu0, pu1, site.hv0, va, 0.0, zt)      # 문 남쪽
        site.box(bm, pu0, pu1, vb, site.hv1, 0.0, zt)      # 문 북쪽
        site.box(bm, pu0, pu1, va, vb, ph, zt)             # 인방 위
    # 중앙 기둥
    site.box(bm, site.hcu - site.pier_side / 2.0, site.hcu + site.pier_side / 2.0,
             site.hcv - site.pier_side / 2.0, site.hcv + site.pier_side / 2.0,
             0.0, site.spring)


# ------------------------------------------------------------------ 빌드


def set_collider_visible(ob, on):
    """콜라이더를 렌더·뷰포트에서 켜고 끈다.

    ⚠ `export_overdare.collect_units()` 는 **`hide_render` 가 켜진 오브젝트를
    건너뛴다.** 즉 렌더에서 숨기면 오버데어로도 안 나간다. 평소에는 꺼 두되
    **발행 직전에 켜야** Part 가 만들어진다.
    """
    ob.hide_render = not on
    ob.hide_viewport = not on
    try:
        ob.hide_set(not on)
    except RuntimeError:
        pass                      # 뷰 레이어가 없는 헤드리스에서는 무시


def studio(site, exposure=-0.6):
    """실내 조명·카메라·월드. 검수용 고정 리그다.

    ⚠ 실내는 **창 8개가 유일한 자연광**이라 노출을 잘못 잡으면 판정이 안 된다.
      EEVEE 레거시는 월드광을 모든 면에 균일하게 먹여서 **밝다고 구멍인지
      알 수 없다.** 구멍 판정은 눈이 아니라 `scene.ray_cast` 로 한다.
    """
    S = bpy.context.scene
    try:
        S.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        S.render.engine = 'BLENDER_EEVEE'

    w = bpy.data.worlds.get("KI_World") or bpy.data.worlds.new("KI_World")
    S.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.55, 0.62, 0.75, 1.0)     # 흐린 모스크바 하늘
    bg.inputs[1].default_value = 1.2

    def add(data, name, loc=None):
        ob = bpy.data.objects.new(name, data)
        S.collection.objects.link(ob)
        if loc:
            ob.location = loc
        return ob

    ld = bpy.data.lights.new("KI_Sun", 'SUN')
    ld.energy, ld.angle = 3.0, math.radians(2.0)
    add(ld, "KI_Sun").rotation_euler = (math.radians(58), 0.0, math.radians(35))

    # 판카딜로 자리. 실제 조명기구는 아직 없고 빛만 먼저 세운다.
    for i, (dx, dy) in enumerate([(-6, -6), (6, -6), (-6, 6), (6, 6)]):
        ld = bpy.data.lights.new("KI_lamp%d" % i, 'POINT')
        ld.energy, ld.shadow_soft_size = 260.0, 0.6
        ld.color = (1.0, 0.86, 0.66)
        add(ld, "KI_lamp%d" % i, (site.hcu + dx, site.hcv + dy, 5.6))

    cd = bpy.data.cameras.new("KI_Cam")
    cd.lens = 16.0
    cam = add(cd, "KI_Cam", (site.hcu + 9.2, site.hcv - 9.2, 1.65))
    d = Vector((site.hcu - 1.0, site.hcv + 2.0, 4.2)) - cam.location
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    S.camera = cam

    S.render.resolution_x, S.render.resolution_y = 1280, 800
    S.view_settings.exposure = exposure
    return cam


def build(seg=14, collider=True, portal_bay=0, podklet=True):
    """방 하나를 원점에 세운다.

    `granovitaya.build_shell()` · `build_interior()` 를 그대로 부른다.
    러스티케이션과 지붕은 외피라 만들지 않는다.

    ⚠ **сени 서쪽 외벽에 문을 내지 않는다.** 계획에는 「서쪽 개구부 + 랜딩」이
      있었지만, 밖이 없는데 문을 내면 방에 구멍이 하나 생길 뿐이다(계획의 다른
      목표인 「방을 닫는다」와 정면으로 부딪힌다). 스폰은 сени 안에 둔다 —
      `spawn_point()` 참조.
    """
    # ⚠ **이걸 빼먹으면 재질이 통째로 안 붙는다.** `hanok.get_mat()` 은 이미
    #   있는 것을 찾아올 뿐 만들지 않아서, `bm_to_object` 가 None 을 append 하고
    #   빈 슬롯이 남는다. 그러면 렌더가 블렌더 기본 흰색으로 나오는데, 회벽으로
    #   칠한 것과 구별이 안 돼서 한동안 모르고 지나갔다.
    hanok.setup_materials()

    site = Site()
    portal = portal_rect(site, bay=portal_bay)

    bm_wall, bm_rust = bmesh.new(), bmesh.new()
    granovitaya.build_shell(site, bm_wall, bm_rust, rustication=False,
                            portal=[portal])
    bm_rust.free()

    pod = Podklet(site) if podklet else None
    gap = (pod.stair_v0, pod.stair_v1) if pod else None

    bm_floor, bm_pier, bm_vault, bm_dado = (bmesh.new() for _ in range(4))
    info = granovitaya.build_interior(site, bm_floor, bm_pier, bm_vault,
                                      bm_dado, seg=seg, portal=portal,
                                      seni_floor_gap=gap)

    bm_cap = bmesh.new()
    build_cap(site, bm_cap)

    bm_grille = bmesh.new()
    build_grilles(site, bm_grille)
    build_seni_ribs(site, bm_vault)          # 리브는 볼트와 같은 회벽이다

    bm_imp = bmesh.new()
    build_impost(site, bm_imp)

    # 재질 — 이 방은 바닥부터 볼트까지 **전면 프레스코**다. 흰 회벽으로 두면
    # 블록아웃으로 보인다. 아랫층만 칠하지 않은 석조로 두어 두 층을 가른다.
    made = [(bm_wall,   'wall',   "파세트실내_벽체",   'fresco_gold'),
            (bm_vault,  'vault',  "파세트실내_볼트",   'fresco_gold'),
            (bm_pier,   'pier',   "파세트실내_기둥",   'fresco_gold'),
            (bm_dado,   'dado',   "파세트실내_다도",   'fresco_band'),
            (bm_imp,    'impost', "파세트실내_임포스트", 'whitewash'),
            (bm_floor,  'floor',  "파세트실내_바닥",   'floor_stone'),
            (bm_cap,    'cap',    "파세트실내_천장캡", 'fresco_gold'),
            (bm_grille, 'grille', "파세트실내_창살",   'iron_dark')]

    if pod is not None:
        bm_pw, bm_pf, bm_pp, bm_st = (bmesh.new() for _ in range(4))
        build_podklet(pod, bm_pw, bm_pf, bm_pp, bm_st)
        made += [(bm_pw, 'p_wall',  "파세트실내_하층벽",   'undercroft'),
                 (bm_pf, 'p_floor', "파세트실내_하층바닥", 'floor_rough'),
                 (bm_pp, 'p_pier',  "파세트실내_하층기둥", 'undercroft'),
                 (bm_st, 'stair',   "파세트실내_계단",     'undercroft')]

    if collider:
        bm_col = bmesh.new()
        build_collider(site, bm_col, portal=portal)
        made.append((bm_col, 'collider', "파세트실내_콜라이더", 'plaster'))

    # ⚠ 상자로 지은 것에 `recalc_face_normals` 를 걸지 마라. `Site.box()` 는
    #   이미 바깥쪽 감기로 만들고, 겹친 상자에서는 recalc 가 안팎을 못 가려
    #   **실내 쪽 면을 뒤집는다** — 그러면 방 안이 통째로 까맣게 렌더된다.
    #   볼트만 부채꼴 웹을 이어 붙인 것이라 recalc 가 필요하다.
    RECALC = {'vault'}
    objs = {}
    for bm, key, name, mat in made:
        # ⚠ 박스 전용 메시에는 `remove_doubles` 를 걸지 않는다.
        #   맞닿은 상자끼리 정점이 병합되면 연결 성분이 8정점을 넘어
        #   `export_overdare.extract_boxes()` 가 **거부한다** → Part 가 아니라
        #   일반 메시로 나가고, 그러면 걸을 수 없다. 실제로 다도(상자 4)와
        #   콜라이더(상자 6)가 이렇게 떨어졌다. 상자 하나 안에는 겹친 정점이
        #   없으므로 걸어 봐야 얻을 것도 없다.
        if key not in PART_KEYS:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
        if key in RECALC:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        objs[key] = hanok.bm_to_object(bm, name, mat, hanok.new_collection(COLL[key]))

    if collider:
        set_collider_visible(objs['collider'], False)

    info.update({'wall_top': site.wall_top, 'cornice': site.cornice,
                 'lu': site.lu, 'lv': site.lv, 'hall': site.hall,
                 'u': (site.u0, site.u1), 'v': (site.v0, site.v1),
                 'portal': portal, 'spawn': spawn_point(site, portal)})
    if pod is not None:
        info.update({'podklet_floor': pod.floor, 'podklet_ceil': pod.ceil,
                     'podklet_clear': pod.clear_h(), 'piers': len(pod.piers),
                     'stair_v': (pod.stair_v0, pod.stair_v1)})
    return site, objs, info


def spawn_point(site, portal):
    """오버데어 스폰 자리 — сени 안, 포털을 마주 보는 지점.

    밖이 없으니 밖에서 들어올 수 없다. 대신 сени 에서 시작해 포털을 지나
    대홀로 들어가게 한다. 걷기 검증도 이 경로로 한다.
    """
    va, vb = portal[0], portal[1]
    su0 = site.u0 + site.seni_o
    su1 = site.hu0 - site.w_seni
    return ((su0 + su1) / 2.0, (va + vb) / 2.0, 0.0)
