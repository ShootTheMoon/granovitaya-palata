# -*- coding: utf-8 -*-
"""붉은광장 — 포장 + 성 바실리 대성당 · GUM · 국립역사박물관 · 레닌묘.

크렘린 **밖**이다. 성벽 동쪽 면에 붙어 있고, 1508~1516년에 판 알레비조프
해자가 1813~14년에 매립되면서 지금의 광장이 됐다.

⚠ **광장 크기에 상충이 있다.**
    공표     330 × 70 m = 23,100 m²   (ru 출처. 산술이 맞는다)
    en.wiki  73,000 m²                 (330×70 과 모순)
    OSM      412.8 × 135.6 m = 31,814 m²  (relation 1577673 실측)
  OSM 폴리곤이 큰 것은 역사박물관 옆 통로와 바실리옙스키 스푸스크까지
  포함하기 때문이다. **포장은 OSM 폴리곤을 쓰고**, 330 × 70 은 광장 본체의
  치수로 따로 기록한다. 둘은 다른 것을 재고 있다.

성 바실리 대성당
    9개 예배당이 하나의 기단 위에 서고 10번째가 1588년에 붙었다.
    가운데 텐트지붕 탑을 8개 양파돔이 둘러싼다 — 4개는 축 방향(크고 낮음),
    4개는 대각선 방향(작고 더 낮음)이다.
    **돔이 다색인 것이 이 건물의 정체성이다.** 크렘린 3대 성당이 전부 금박인
    것과 달리 여기만 나선·마름모 무늬의 원색이고, 금박 하나로 뭉개면
    알아볼 수가 없다. 1680년대 채색이 현재 모습이다.
    ⚠ OSM 릴레이션이 둘이다 — 3030568(46.5×51.8, 기단·갤러리 포함, height=67)
      과 3224486(33.1×33.7, 본체로 보임). 공표 폭 38 m 가 그 사이에 있다.
"""

import math

import bmesh

import hanok
from kremlin import dome, geo_kr, measured, palace
from kremlin.measured import val

GROUND = 0.0

# 성 바실리 — OSM 릴레이션과 공표 치수
SB_REL = "3030568"
SB_CORE = 33.4          # m. relation 3224486 실측 (본체)
SB_PODIUM = 3.2         # 기단 높이. ⚠ derived

# 돔 색. 실제로는 8개가 전부 다른 무늬라 색만으로 근사한다.
SB_DOME_MATS = ('dome_red', 'dome_green', 'dome_blue', 'dome_ochre')


def _ring_of(osm, rid, simplify=0.8):
    f = osm.by_id(rid, "relation") or osm.by_id(rid, "way")
    if f is None:
        return None
    rr = osm.rings(f)
    if not rr:
        return None
    ring = geo_kr.project(max(rr, key=lambda r: abs(geo_kr.poly_area(r))))
    if geo_kr.poly_area(ring) < 0:
        ring.reverse()
    ring = palace._dp(ring, simplify)
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    return ring


def build_paving(bm, ring, z=0.0, thick=0.35):
    """광장 포장 슬래브. 얇은 판이면 낮은 각도에서 종잇장으로 보인다."""
    lo = [bm.verts.new((p[0], p[1], z - thick)) for p in ring]
    hi = [bm.verts.new((p[0], p[1], z)) for p in ring]
    bm.faces.new(list(reversed(lo)))
    bm.faces.new(hi)
    n = len(ring)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    return abs(geo_kr.poly_area(ring))


def build_mausoleum(bm, cx, cy, yaw):
    """레닌묘 — 5단 계단식. 정면 24 m, 높이 12 m.

    ⚠ OSM 폴리곤(30.4 × 38.0 m)은 양옆 귀빈 관람대까지 포함한 것이다.
    본체는 공표 24 × 12 m 를 쓰고, 관람대는 낮은 단으로 따로 둔다.
    """
    M = measured.LENIN_MAUSOLEUM
    L = val(M, 'facade_len')
    H = val(M, 'height')
    n = val(M, 'steps')
    c, s = math.cos(yaw), math.sin(yaw)

    def box(le, ln, z0, z1):
        pts = []
        for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            u, v = su * le / 2.0, sv * ln / 2.0
            pts.append((cx + u * c - v * s, cy + u * s + v * c))
        a = [bm.verts.new((p[0], p[1], z0)) for p in pts]
        b = [bm.verts.new((p[0], p[1], z1)) for p in pts]
        bm.faces.new(list(reversed(a)))
        bm.faces.new(b)
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((a[i], a[j], b[j], b[i]))

    # 5단이 위로 갈수록 줄어든다. 맨 위는 열주 위 평판
    for i in range(n):
        f0, f1 = i / float(n), (i + 1) / float(n)
        k = 1.0 - 0.62 * f0
        box(L * k, L * 0.62 * k, GROUND + H * f0, GROUND + H * f1)
    # 양옆 관람대
    for sgn in (-1.0, 1.0):
        ox = sgn * (L / 2.0 + 9.0)
        box2x = cx + ox * c
        box2y = cy + ox * s
        pts = []
        for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            u, v = su * 9.0, sv * 5.5
            pts.append((box2x + u * c - v * s, box2y + u * s + v * c))
        a = [bm.verts.new((p[0], p[1], GROUND)) for p in pts]
        b = [bm.verts.new((p[0], p[1], GROUND + 3.4)) for p in pts]
        bm.faces.new(list(reversed(a)))
        bm.faces.new(b)
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((a[i], a[j], b[j], b[i]))
    return H


def build_st_basil(bm, bm_domes, cx, cy, yaw):
    """성 바실리 대성당 — 중앙 텐트탑 + 8개 양파돔 예배당.

    높이는 공표 65 m(십자가 포함), 중앙 텐트 47 m 를 기준으로 층을 나눈다.
    """
    B = measured.ST_BASIL
    H = val(B, 'height')
    Hc = val(B, 'height_central')
    z0 = GROUND + SB_PODIUM
    r_core = SB_CORE / 2.0

    # 기단(гульбище) — 팔각
    dome._revolve(bm, cx, cy, GROUND,
                  [(r_core * 1.30, 0.0), (r_core * 1.26, SB_PODIUM)], 8)

    # --- 중앙 텐트탑 (сhatyor). 팔각 몸통 → 코코시닉 → 텐트 → 소구 → 십자가
    rc = r_core * 0.34
    body_h = Hc * 0.53
    dome._revolve(bm, cx, cy, z0, [(rc, 0.0), (rc * 0.94, body_h)], 8)
    dome.kokoshnik_ring(bm, cx, cy, z0 + body_h, rc * 0.96, 8,
                        rc * 0.62, body_h * 0.13, depth=rc * 0.14, phase=yaw)
    tent_h = Hc - body_h
    dome.tent(bm_domes, cx, cy, z0 + body_h, rc * 1.0, tent_h,
              sides=8, flare=0.08)
    ztop = z0 + body_h + tent_h
    hd = dome.onion(bm_domes, cx, cy, ztop, rc * 0.30, seg=16, steps=16)
    dome.ball(bm, cx, cy, ztop + hd, rc * 0.13, 10)
    dome.cross(bm, cx, cy, ztop + hd + rc * 0.26,
               GROUND + H - (ztop + hd + rc * 0.26), yaw=yaw)

    # --- 8개 예배당. 축 4개는 크고, 대각 4개는 작다
    n_dome = 0
    for k in range(8):
        a = yaw + math.pi * k / 4.0
        axis = (k % 2 == 0)
        rad = r_core * (0.62 if axis else 0.60)
        px, py = cx + rad * math.cos(a), cy + rad * math.sin(a)
        rr = r_core * (0.215 if axis else 0.160)
        bh = Hc * (0.40 if axis else 0.30)
        dh = bh * 0.42
        # 팔각 몸통 + 코코시닉 다단 + 드럼 + 양파돔 + 십자가
        dome._revolve(bm, px, py, z0, [(rr, 0.0), (rr * 0.95, bh)], 8)
        for t in range(2):
            dome.kokoshnik_ring(bm, px, py, z0 + bh * (0.86 + 0.09 * t),
                                rr * (0.97 - 0.10 * t), 8,
                                rr * 0.55, bh * 0.10, depth=rr * 0.13, phase=a)
        dome.drum(bm, px, py, z0 + bh, rr * 0.66, dh, seg=14)
        mat = SB_DOME_MATS[k % len(SB_DOME_MATS)]
        hh = dome.onion(bm_domes[mat], px, py, z0 + bh + dh, rr * 0.66,
                        seg=18, steps=18)
        dome.ball(bm, px, py, z0 + bh + dh + hh, rr * 0.16, 10)
        dome.cross(bm, px, py, z0 + bh + dh + hh + rr * 0.30,
                   rr * 1.25, yaw=a)
        n_dome += 1
    return GROUND + H, n_dome


def build(coll=None, osm=None):
    coll = coll or hanok.new_collection("붉은광장_포장")
    coll_b = hanok.new_collection("붉은광장_건물")
    coll_v = hanok.new_collection("붉은광장_성바실리")
    osm = osm or geo_kr.Osm()
    st = {'built': [], 'err': [], 'missing': [], 'area': 0.0, 'sb_domes': 0}

    # --- 1. 포장
    bm_pave = bmesh.new()
    ring = _ring_of(osm, "1577673", simplify=1.2)
    if ring:
        st['area'] = build_paving(bm_pave, ring)
    else:
        st['missing'].append('붉은광장 포장')
    hanok.bm_to_object(bm_pave, "붉은광장_포장_석재", 'granite_d', coll)

    # --- 2. 주변 건물 (폴리곤 압출). palace 의 빌더를 그대로 쓴다
    bm = bmesh.new()
    bm_roof = bmesh.new()
    BUILDINGS = {
        # 이름: (rel, 높이, 층수, 로툰다)
        'GUM': ("3330565", 22.0, 3, None),
        '국립역사박물관': ("5963922", 28.0, 3, None),
        '마네지': ("3062892", 24.0, 1, None),
    }
    for name, (rid, h, lv, rot) in BUILDINGS.items():
        r = _ring_of(osm, rid, simplify=1.0)
        if r is None:
            st['missing'].append(name)
            continue
        try:
            palace.build_one(bm, bm_roof, name, r, h, lv, rot)
            st['built'].append(name)
        except Exception as exc:                  # noqa: BLE001
            st['err'].append((name, repr(exc)))

    # --- 3. 레닌묘 — 붉은 화강암이라 따로 굽는다
    bm_mau = bmesh.new()
    M = measured.LENIN_MAUSOLEUM
    try:
        build_mausoleum(bm_mau, 111.7, 232.8, math.radians(48.0))
        st['built'].append('레닌묘')
    except Exception as exc:                      # noqa: BLE001
        st['err'].append(('레닌묘', repr(exc)))

    hanok.bm_to_object(bm, "붉은광장_건물_석조", 'whitewash', coll_b)
    hanok.bm_to_object(bm_roof, "붉은광장_건물_지붕", 'green_roof', coll_b)
    hanok.bm_to_object(bm_mau, "붉은광장_레닌묘", 'granite_red', coll_b)

    # --- 4. 성 바실리 — 돔 색마다 메시를 나눈다
    bm_sb = bmesh.new()
    bm_sbd = {m: bmesh.new() for m in SB_DOME_MATS}
    bm_tent = bmesh.new()

    class _Router(dict):
        """dome 함수에 그대로 넘길 수 있게, 텐트/중앙돔은 bm_tent 로 보낸다."""
        def __getitem__(self, k):
            return dict.__getitem__(self, k)

    router = _Router(bm_sbd)
    try:
        top, nd = build_st_basil(bm_sb, _TentProxy(bm_tent, router),
                                 311.1, 96.4, math.radians(34.0))
        st['sb_domes'] = nd
        st['built'].append('성 바실리 대성당 (정점 %.1f m)' % top)
    except Exception as exc:                      # noqa: BLE001
        st['err'].append(('성 바실리', repr(exc)))

    hanok.bm_to_object(bm_sb, "성바실리_석조", 'brick_red', coll_v)
    hanok.bm_to_object(bm_tent, "성바실리_중앙텐트", 'green_roof', coll_v)
    for m, b in bm_sbd.items():
        if len(b.verts):
            hanok.bm_to_object(b, "성바실리_돔_%s" % m, m, coll_v)
        else:
            b.free()
    return coll, st


class _TentProxy(object):
    """중앙 텐트·중앙 돔은 단일 bmesh 로, 8개 예배당 돔은 색별 bmesh 로 보낸다.

    build_st_basil 이 중앙부에는 이 객체를 bmesh 처럼 쓰고, 예배당에는
    [mat] 로 인덱싱해 색별 bmesh 를 꺼낸다.
    """

    def __init__(self, tent_bm, routes):
        self._t = tent_bm
        self._r = routes

    def __getitem__(self, mat):
        return self._r[mat]

    @property
    def verts(self):
        return self._t.verts

    @property
    def faces(self):
        return self._t.faces
