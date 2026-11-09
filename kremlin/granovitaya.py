# -*- coding: utf-8 -*-
"""파세트궁(Грановитая палата) — 외피 + 실내.

크렘린에서 **실내를 먼저 짓는 첫 건물**이다. 고른 이유는 자료가 유일하게
완결돼 있어서다: Табл.12 에 평면·단면·정면 입면이 다 있고, 상층이 옥좌홀
하나뿐인 단칸 건물이라 도면만으로 내부가 닫힌다.

치수는 전부 `measured.GRANOVITAYA` 에서 읽는다. 2026-08-23 에 Табл.12 를
픽셀로 재서 채워 넣었고, 축척 판정 근거는 거기 주석에 있다.

기하가 닫히는 지점 둘 — 우연이 아니라 검산이다:
  · 스프링잉 3.4 + 베이 반경 5.6 = **9.0** = 문헌 볼트 최고점
  · 큰 창이 바닥 위 4.1~8.1 m 인데 루넷이 3.4~9.0 이라 **창이 루넷 안에 든다**

⚠ `palace.py` 는 이 건물을 안 짓는다. 「OSM 에 개별 매핑이 없다」고 적혀
  있지만 그건 08-18 캐시 기준이고, relation **7679578** 이 실재한다
  (2026-08-23 OSM API 로 받아 `osm/granovitaya.osm` 에 넣었다).
  대크렘린궁 relation 225033 과는 별개다.
"""

import math
import os

import bmesh
from mathutils import Vector

import hanok
from kremlin import dome, geo_kr, measured, vault
from kremlin.measured import val

HERE = os.path.dirname(os.path.abspath(__file__))
OSM_PATH = os.path.join(HERE, "osm", "granovitaya.osm")
REL = "7679578"

COLL = "크렘린_파세트궁"
COLL_FLOOR = "크렘린_파세트궁_바닥"


# ------------------------------------------------------------------ 발자국

def footprint():
    """(중심 x, 중심 y, yaw°, 장변, 단변). OBB 기준이다.

    무게중심이 아니라 **OBB 중심**을 쓴다 — 실측 상자를 발자국에 맞추는
    조작이므로 기준도 상자 중심이어야 한다. 성바실리에서 무게중심을 썼다가
    5.1 m 어긋난 적이 있다.
    """
    o = geo_kr.Osm(OSM_PATH)
    f = o.by_id(REL, kind="relation")
    pts = list(geo_kr.project(list(o.rings(f))[0]))
    yaw = geo_kr.principal_angle(pts)
    a = math.radians(-yaw)
    c, s = math.cos(a), math.sin(a)
    xs = [p[0] * c - p[1] * s for p in pts]
    ys = [p[0] * s + p[1] * c for p in pts]
    cu, cv = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
    a = math.radians(yaw)
    cx = cu * math.cos(a) - cv * math.sin(a)
    cy = cu * math.sin(a) + cv * math.cos(a)
    return cx, cy, yaw, max(xs) - min(xs), max(ys) - min(ys)


# ------------------------------------------------------------------ 배치

class Site(object):
    """로컬(u = 장변, v = 단변) → 월드 변환과 층 레벨을 들고 있는 상자."""

    def __init__(self):
        g = measured.GRANOVITAYA
        self.cx, self.cy, self.yaw, self.ext_u, self.ext_v = footprint()
        a = math.radians(self.yaw)
        self._c, self._s = math.cos(a), math.sin(a)

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

        self.floor = val(g, 'podklet_h')
        self.spring = self.floor + val(g, 'vault_spring_h')
        self.crown = self.floor + val(g, 'vault_h')
        self.wall_top = val(g, 'wall_top')
        self.apex = val(g, 'roof_apex')
        self.sill = self.floor + val(g, 'window_sill')
        self.head = self.floor + val(g, 'window_head')

        self.hu0 = -self.lu / 2.0 + self.seni_o + self.seni + self.w_seni
        self.hu1 = self.hu0 + self.hall
        self.hv0 = -self.lv / 2.0 + self.w_north
        self.hv1 = self.hv0 + self.hall
        self.hcu = (self.hu0 + self.hu1) / 2.0
        self.hcv = (self.hv0 + self.hv1) / 2.0

    def w(self, u, v):
        """로컬 → 월드 (x, y)."""
        return (self.cx + u * self._c - v * self._s,
                self.cy + u * self._s + v * self._c)

    def box(self, bm, u0, u1, v0, v1, z0, z1):
        """로컬 축정렬 상자를 월드에 놓는다. yaw 때문에 8점을 직접 만든다."""
        if u1 - u0 < 1e-6 or v1 - v0 < 1e-6 or z1 - z0 < 1e-6:
            return
        pts = [self.w(u, v) for u, v in
               ((u0, v0), (u1, v0), (u1, v1), (u0, v1))]
        lo = [bm.verts.new((x, y, z0)) for x, y in pts]
        hi = [bm.verts.new((x, y, z1)) for x, y in pts]
        bm.faces.new(lo[::-1])
        bm.faces.new(hi)
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((lo[i], lo[j], hi[j], hi[i]))


# ------------------------------------------------------------------ 벽

def _half(z, zs, zh, half, arched):
    """개구부 중심에서의 반폭. arched 면 상부가 반원으로 닫힌다.

    스프링잉을 `zh - half` 로 두면 아치가 정확히 반원이 되고 마루가 zh 에 온다.
    """
    if not arched:
        return half
    za = zh - half
    if z <= za:
        return half
    d = z - za
    return math.sqrt(half * half - d * d) if d < half else 0.0


def _run(site, bm, along_u, f0, f1, t0, t1, z0, z1, gaps=()):
    """벽체 한 줄. gaps 는 [(t_a, t_b, z_a, z_b), ...] **사각 공동**이다.

    아치머리와 사면 여벽은 여기서 만들지 않는다 — `_window()` 가 그 공동 안에
    따로 채워 넣는다. 처음엔 두께를 여러 겹으로, 높이를 여러 단으로 잘라
    상자를 쌓아서 사면과 아치를 흉내 냈는데, 분할을 24×6 까지 올려도
    **문설주가 골판처럼 계단으로 보였다.** 상자 적층으로는 매끈한 경사가
    원리적으로 안 나온다.
    """
    def emit(a, b, za, zb):
        if along_u:
            site.box(bm, a, b, f0, f1, za, zb)
        else:
            site.box(bm, f0, f1, a, b, za, zb)

    if not gaps:
        emit(t0, t1, z0, z1)
        return
    gaps = sorted(gaps)
    zg0 = min(g[2] for g in gaps)
    zg1 = max(g[3] for g in gaps)
    emit(t0, t1, z0, zg0)
    emit(t0, t1, zg1, z1)
    cur = t0
    for ga, gb, _, _ in gaps:
        emit(cur, ga, zg0, zg1)
        cur = gb
    emit(cur, t1, zg0, zg1)


def _hex(site, bm, along_u, quad_out, quad_in, f_out, f_in):
    """(t, z) 네 점씩인 두 면을 이어 육면체 하나를 만든다.

    두 면의 t 가 다르면 경사면이 생긴다 — 사면 여벽의 문설주가 이것이다.

    감기를 손으로 맞추지 않는다. 아치머리에서 좌우 대칭 때문에 부호가
    갈리는데 그걸 일일이 뒤집다 보면 **일부가 반대로 서서 실내에서 검게
    보인다** (실제로 56면이 그랬다). 그래서 만들고 나서 **자기 중심 기준으로**
    바깥을 향하도록 돌린다 — 국소 판정이라 겹친 상자에도 안전하다.
    """
    def V(t, z, f):
        xy = site.w(t, f) if along_u else site.w(f, t)
        return bm.verts.new((xy[0], xy[1], z))
    a = [V(t, z, f_out) for t, z in quad_out]
    b = [V(t, z, f_in) for t, z in quad_in]
    if len({v.co.to_tuple(4) for v in a + b}) < 5:
        return                                    # 납작하게 뭉갠 것은 버린다
    ctr = sum((v.co for v in a + b), Vector()) / 8.0
    faces = [a, b] + [[a[i], a[(i + 1) % 4], b[(i + 1) % 4], b[i]] for i in range(4)]
    for loop in faces:
        try:
            f = bm.faces.new(loop)
        except ValueError:
            continue
        f.normal_update()
        if f.normal.dot(f.calc_center_median() - ctr) < 0.0:
            f.normal_flip()


def _window(site, bm, along_u, f_out, f_in, ta, tb, zs, zh, splay, steps=14):
    """사각 공동 안을 채워 **반원 아치 + 안쪽으로 넓어지는 사면 여벽**을 만든다.

    ta~tb 는 **안쪽(넓은 쪽)** 개구부 폭이다. 바깥은 splay 만큼 좁다.

    문설주는 z 에 따라 변하지 않으므로 **평면 쐐기 하나로** 만든다 — 계단이
    생길 여지가 없다. 아치머리만 z 에 따라 폭이 바뀌므로 분할한다.
    """
    c = (ta + tb) / 2.0
    hi = (tb - ta) / 2.0
    ho = max(0.15, hi - splay)
    zsp_i, zsp_o = zh - hi, zh - ho          # 각 면의 아치 스프링잉

    # 1) 문설주 — 스프링잉 아래는 폭이 일정하다. 좌우 각각 쐐기 하나.
    for sgn in (-1, 1):
        to, ti = c + sgn * ho, c + sgn * hi
        eo, ei = (ta, ti) if sgn < 0 else (tb, ti)
        quad_o = [(eo if sgn < 0 else to, zs), (to if sgn < 0 else eo, zs),
                  (to if sgn < 0 else eo, zsp_i), (eo if sgn < 0 else to, zsp_i)]
        quad_i = [(ei if sgn < 0 else ti, zs), (ti if sgn < 0 else ei, zs),
                  (ti if sgn < 0 else ei, zsp_i), (ei if sgn < 0 else ti, zsp_i)]
        _hex(site, bm, along_u, quad_o, quad_i, f_out, f_in)

    # 2) 아치머리 — 스프링잉 위. 폭이 z 에 따라 줄어드니 여기만 나눈다.
    for k in range(steps):
        z0 = zsp_i + (zh - zsp_i) * k / steps
        z1 = zsp_i + (zh - zsp_i) * (k + 1) / steps
        for zz, zzn in ((z0, z1),):
            for sgn in (-1, 1):
                def hw(z, h, zsp):
                    d = z - zsp
                    return h if d <= 0 else (math.sqrt(h * h - d * d) if d < h else 0.0)
                oa, ob_ = hw(zz, ho, zsp_o), hw(zzn, ho, zsp_o)
                ia, ib = hw(zz, hi, zsp_i), hw(zzn, hi, zsp_i)
                eo = ta if sgn < 0 else tb
                po = [(eo, zz), (c + sgn * oa, zz), (c + sgn * ob_, zzn), (eo, zzn)]
                pi = [(eo, zz), (c + sgn * ia, zz), (c + sgn * ib, zzn), (eo, zzn)]
                if sgn > 0:
                    po = po[::-1]; pi = pi[::-1]
                _hex(site, bm, along_u, po, pi, f_out, f_in)


def _windows(t0, t1, n, w, zs, zh):
    """벽 한 줄에 창 n 개를 고르게."""
    pitch = (t1 - t0) / n
    return [(t0 + pitch * (i + 0.5) - w / 2.0,
             t0 + pitch * (i + 0.5) + w / 2.0, zs, zh) for i in range(n)]


def _clip(site, wins, t0, margin=0.30):
    """창머리를 그 자리의 **볼트 아치선 아래**로 눌러 준다.

    루넷은 가운데가 높고 양끝이 스프링잉까지 내려온다. 창을 일정 높이로
    뚫으면 가장자리 창이 **볼트를 뚫고 지붕 공간으로 열린다** — 실제로
    실내 렌더 우상단에 지붕 밑이 비쳤다. 창 폭 전체에서 아치가 가장 낮은
    지점을 찾아 거기서 margin 만큼 내린다.

    `t0` 는 **그 벽이 도는 방향의 베이 원점**이다. u 방향으로 도는 벽은
    `hu0`, v 방향은 `hv0`.
    ⚠ 예전에는 「어느 벽이든 루넷 배치는 같다」며 `hv0` 를 박아 썼는데
      틀렸다. `hu0` 와 `hv0` 는 벽 두께가 달라 3.7 m 어긋나 있어서, 위상이
      밀린 채 계산된 남측 창 둘이 **머리가 문턱보다 낮게** 잘려 나갔다
      (뒤집힌 개구부 → 벽에 구멍). 실내 빌드에서 `ray_cast` 로 잡았다.
    """
    bay = site.hall / 2.0
    r = bay / 2.0
    out = []
    for ta, tb, zs, zh in wins:
        lo = None
        for t in (ta, (ta + tb) / 2.0, tb):
            p = (t - t0) % bay          # 베이 안에서의 위치
            d = abs(r - p)
            h = site.spring + (math.sqrt(r * r - d * d) if d < r else 0.0)
            lo = h if lo is None else min(lo, h)
        out.append((ta, tb, zs, min(zh, lo - margin)))
    return out


def build_shell(site, bm, bm_rust, rustication=True, portal=()):
    """외벽 + 창. 러스티케이션은 머티리얼이 달라 별도 bmesh 로 뺀다.

    `portal` 은 сени 격벽에 낼 **사각 개구부** 목록 [(v_a, v_b, z_a, z_b), ...] 다.
    빈 값이면 격벽이 통짜다(외피 빌드의 기존 동작). 아치가 아니라 사각인 이유는
    Табл.15 의 개구부가 평인방이기 때문이다 — 오지형 첨두는 그 위에 얹힌 장식이지
    개구부 자체가 아니다. 조각 틀은 별도 소품으로 붙인다.
    """
    u0, u1 = -site.lu / 2.0, site.lu / 2.0
    v0, v1 = -site.lv / 2.0, site.lv / 2.0
    zt = site.wall_top

    # 볼트 아치의 가장자리가 벽 안쪽면과 **정확히 같은 평면**이라 그대로 두면
    # z-파이팅으로 하늘이 비치는 실선이 생긴다. 벽을 이만큼 안쪽으로 물려
    # 볼트 끝을 묻는다. 4 cm 는 도면 판독 정밀도 아래라 치수에 영향이 없다.
    b = 0.04

    # 하부 подклет — 통짜
    site.box(bm, u0, u1, v0, v1, 0.0, site.floor)

    win_e = _clip(site, _windows(site.hv0, site.hv1, 4, 1.9, site.sill, site.head),
                  site.hv0)
    win_s = _clip(site, _windows(site.hu0, site.hu1, 4, 1.9, site.sill, site.head),
                  site.hu0)

    # 동측(러스티케이션 면) · 남측 · 북측 · 서측 내벽 · сени 외벽
    _run(site, bm, False, site.hu1 - b, u1, site.hv0, site.hv1,
         site.floor, zt, win_e)
    _run(site, bm, True, site.hv1 - b, v1, site.hu0, site.hu1,
         site.floor, zt, win_s)
    sp = val(measured.GRANOVITAYA, 'window_splay')
    for ta, tb, zs, zh in win_e:
        _window(site, bm, False, u1, site.hu1 - b, ta, tb, zs, zh, sp)
    for ta, tb, zs, zh in win_s:
        _window(site, bm, True, v1, site.hv1 - b, ta, tb, zs, zh, sp)
    _run(site, bm, True, v0, site.hv0 + b, u0, u1, site.floor, zt)
    _run(site, bm, False, site.hu0 - site.w_seni, site.hu0 + b,
         site.hv0, site.hv1, site.floor, zt, tuple(portal))
    _run(site, bm, False, u0, u0 + site.seni_o, v0, v1, site.floor, zt)
    # 모서리 채움 + сени 남북 마구리
    site.box(bm, site.hu1, u1, site.hv1, v1, site.floor, zt)
    site.box(bm, u0 + site.seni_o, site.hu0, site.hv1, v1, site.floor, zt)

    if rustication:
        _rustication(site, bm_rust, u1, site.hv0, site.hv1, site.floor, zt,
                     skip=win_e)


def _rustication(site, bm, u_face, v0, v1, z0, z1, step=0.62, out=0.16,
                 skip=()):
    """면치기 블록을 한 면에 격자로 붙인다. 블록 하나가 사각뿔이다.

    **메시에 실제로 돌출시킨다.** 텍스처 단계의 delight 가 그림자를 지우므로
    노멀맵으로는 이 건물의 유일한 식별자가 살지 않는다.

    `skip` 은 개구부 목록 (t_a, t_b, z_a, z_b). 안 넘기면 격자가 창까지
    덮어 버려 창이 사라진다 — 첫 빌드에서 실제로 그렇게 됐다.
    """
    def blocked(vc, zc):
        for ta, tb, za_, zb_ in skip:
            if ta - step * 0.5 <= vc <= tb + step * 0.5 and \
               za_ - step * 0.5 <= zc <= zb_ + step * 0.5:
                return True
        return False

    nv = max(1, int((v1 - v0) / step))
    nz = max(1, int((z1 - z0) / step))
    sv, sz = (v1 - v0) / nv, (z1 - z0) / nz
    for i in range(nv):
        for j in range(nz):
            va, vb = v0 + sv * i, v0 + sv * (i + 1)
            za, zb = z0 + sz * j, z0 + sz * (j + 1)
            if blocked((va + vb) / 2.0, (za + zb) / 2.0):
                continue
            base = ((va, za), (vb, za), (vb, zb), (va, zb))
            bv = [bm.verts.new((site.w(u_face, v)[0], site.w(u_face, v)[1], z))
                  for v, z in base]
            tx, ty = site.w(u_face + out, (va + vb) / 2.0)
            tip = bm.verts.new((tx, ty, (za + zb) / 2.0))
            for k in range(4):
                bm.faces.new((bv[k], bv[(k + 1) % 4], tip))


# ------------------------------------------------------------------ 실내

def _dado(site, bm, h, out=0.13, gap=None):
    """벽 하부를 도는 붙박이 다도 띠(лавки 겸용).

    `gap` 은 서벽(сени 격벽) 쪽 띠를 끊을 구간 (v_a, v_b, ...) 이다. 포털이
    거기 나므로 안 끊으면 **문 앞을 높이 1.2 m 턱이 가로막는다** — 실내
    빌드에서 `ray_cast` 가 눈높이 1.0 에서 다도에 맞는 것으로 잡아냈다.

    Табл.12 단면에서 전폭을 가로지르는 y≈385 의 이중선이 이것이다. 처음에
    그걸 바닥선으로 읽었다가 볼트 높이가 안 맞았는데, 바닥은 그보다 아래
    (해칭 상단 y≈430)이고 그 사이 45 px = 1.18 m 가 다도 높이다.
    Табл.14 대홀 사진에도 벽 밑을 도는 밝은 띠로 보인다.
    """
    z0, z1 = site.floor, site.floor + h
    a0, a1 = site.hu0, site.hu1
    b0, b1 = site.hv0, site.hv1
    site.box(bm, a0, a1, b0, b0 + out, z0, z1)
    site.box(bm, a0, a1, b1 - out, b1, z0, z1)
    site.box(bm, a1 - out, a1, b0 + out, b1 - out, z0, z1)
    # 서벽 띠 — 포털이 있으면 끊는다
    w0, w1 = b0 + out, b1 - out
    if gap is None:
        site.box(bm, a0, a0 + out, w0, w1, z0, z1)
    else:
        va, vb = gap[0], gap[1]
        site.box(bm, a0, a0 + out, w0, min(w1, va), z0, z1)
        site.box(bm, a0, a0 + out, max(w0, vb), w1, z0, z1)


def build_interior(site, bm_floor, bm_pier, bm_vault, bm_dado, seg=14,
                   portal=None, seni_floor_gap=None):
    """바닥·기둥·볼트·다도·сени 볼트.

    `portal` 이 있으면 다도 띠를 그 자리에서 끊고, **격벽 밑 바닥을 메운다.**
    ⚠ 홀 바닥과 сени 바닥은 원래 격벽 두께만큼 떨어져 있다. 격벽이 통짜일
      때는 안 보였지만 포털을 뚫으면 **문지방 밑이 그대로 뚫린 구멍**이 된다
      (실내 빌드에서 сени 에서 동쪽·아래로 쏜 광선 35개가 여기로 빠져나갔다).
    """
    site.box(bm_floor, site.hu0, site.hu1, site.hv0, site.hv1,
             site.floor - 0.35, site.floor)
    su0 = -site.lu / 2.0 + site.seni_o
    su1 = site.hu0 - site.w_seni
    # `seni_floor_gap` 은 계단실이다. 아랫층을 지으면 сени 바닥 한쪽을 뚫어
    # 내려가는 구멍을 낸다. (v_a, v_b) 구간을 빼고 깐다.
    if seni_floor_gap is None:
        site.box(bm_floor, su0, su1, site.hv0, site.hv1,
                 site.floor - 0.35, site.floor)
    else:
        ga, gb = seni_floor_gap
        site.box(bm_floor, su0, su1, site.hv0, ga, site.floor - 0.35, site.floor)
        site.box(bm_floor, su0, su1, gb, site.hv1, site.floor - 0.35, site.floor)
    if portal is not None:                     # 격벽 밑 문지방
        site.box(bm_floor, su1, site.hu0, site.hv0, site.hv1,
                 site.floor - 0.35, site.floor)

    cx, cy = site.w(site.hcu, site.hcv)
    vault.pier(bm_pier, cx, cy, site.floor, site.spring, site.pier_side)
    crown, bay = vault.quad_groin(bm_vault, cx, cy, site.spring, site.hall,
                                  seg=seg, thick=0.35)

    _dado(site, bm_dado, val(measured.GRANOVITAYA, 'dado_h'), gap=portal)

    # сени — Табл.13 은 **장식 띠를 두른 횡단 아치가 반복되는** 볼트 갤러리다.
    # 교차볼트는 정사각 베이라야 하므로 한 변을 сени 안목(5.1)에 맞추고,
    # 네 칸을 22.4/4 = 5.6 간격으로 놓는다. 남는 0.5 가 도판의 횡단 아치 띠다.
    # ⚠ 처음엔 한 변을 5.6 으로 잡았다가 сени 안목 5.1 을 **넘어 벽을 뚫었다.**
    # 베이는 5.1(안목) × 5.6(피치) 인 **직사각**이다. 정사각으로 맞추려다
    # 두 번 틀렸다 — 5.6 으로 하면 안목을 넘어 벽을 뚫고, 5.1 로 하면
    # 베이 사이가 0.5 씩 뚫려 지붕 밑이 보인다. 직사각 베이가 정답이고
    # 마루는 짧은 변 기준(2.55)으로 잡는다.
    sbay = site.seni
    srise = sbay / 2.0
    sz0 = site.floor + 2.6
    scu = (su0 + su1) / 2.0
    sx, sy = site.w(scu, (site.hv0 + site.hv1) / 2.0)
    # ⚠ 교차볼트를 네 칸 늘어놓으면 **칸 경계마다 위가 뚫린다** — 정사각(5.6),
    #   직사각(5.1×5.6), 경계에 횡단 아치 띠까지 세 번 시도했으나 다 샜다.
    #   좁고 긴 공간이라 경계 없는 원통 하나가 확실하다.
    #   Табл.13 의 횡단 아치는 나중에 이 위에 리브로 얹는다.
    scrown = vault.barrel(bm_vault, sx, sy, sz0, sbay + 0.12, site.hall + 0.1,
                          along_v=True, seg=22, thick=0.3,
                          yaw_c=site._c, yaw_s=site._s)

    return {'floor': site.floor, 'spring': site.spring, 'crown': crown,
            'bay': bay, 'pier_xy': (cx, cy), 'seni_bay': sbay,
            'seni_crown': scrown}


def build_roof(site, bm):
    """급경사 박공. Табл.12 입면이 보여 주는 형태다."""
    u0, u1 = -site.lu / 2.0, site.lu / 2.0
    v0, v1 = -site.lv / 2.0, site.lv / 2.0
    vc = (v0 + v1) / 2.0
    a = [bm.verts.new((site.w(u, v)[0], site.w(u, v)[1], site.wall_top))
         for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))]
    r0 = bm.verts.new((site.w(u0, vc)[0], site.w(u0, vc)[1], site.apex))
    r1 = bm.verts.new((site.w(u1, vc)[0], site.w(u1, vc)[1], site.apex))
    bm.faces.new((a[0], a[1], r1, r0))
    bm.faces.new((a[2], a[3], r0, r1))
    bm.faces.new((a[1], a[2], r1))
    bm.faces.new((a[3], a[0], r0))


# ------------------------------------------------------------------ 빌드

def build(coll=None, seg=14, rustication=True):
    coll = coll or hanok.new_collection(COLL)
    coll_f = hanok.new_collection(COLL_FLOOR)
    site = Site()

    bm_shell, bm_rust = bmesh.new(), bmesh.new()
    build_shell(site, bm_shell, bm_rust, rustication=rustication)

    bm_floor, bm_pier, bm_vault = bmesh.new(), bmesh.new(), bmesh.new()
    bm_dado = bmesh.new()
    info = build_interior(site, bm_floor, bm_pier, bm_vault, bm_dado, seg=seg)

    bm_roof = bmesh.new()
    build_roof(site, bm_roof)

    made = [(bm_shell, "파세트궁_벽체", 'plaster', coll),
            (bm_pier, "파세트궁_기둥", 'granite', coll),
            (bm_vault, "파세트궁_볼트", 'plaster', coll),
            (bm_dado, "파세트궁_다도", 'granite', coll),
            (bm_roof, "파세트궁_지붕", 'tile', coll),
            (bm_floor, "파세트궁_바닥", 'granite_d', coll_f)]
    if rustication:
        made.insert(1, (bm_rust, "파세트궁_러스티케이션", 'dc_white', coll))

    # ⚠ 상자로 지은 것에는 recalc_face_normals 를 걸지 마라.
    #   `Site.box()` 는 이미 바깥쪽 감기로 만든다. 상자가 서로 겹쳐 있으면
    #   recalc 가 안팎을 못 가려 **실내 쪽 면을 뒤집어 버리고**, 그러면
    #   방 안이 통째로 까맣게 렌더된다. 실제로 그렇게 됐다.
    #   볼트만 부채꼴 웹을 이어 붙인 것이라 recalc 가 필요하다.
    RECALC = {"파세트궁_볼트"}
    for bm, name, mat, c in made:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
        if name in RECALC:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        hanok.bm_to_object(bm, name, mat, c)

    info.update({'yaw': site.yaw, 'center': (site.cx, site.cy),
                 'lu': site.lu, 'lv': site.lv, 'hall': site.hall,
                 'wall_top': site.wall_top, 'apex': site.apex})
    return info
