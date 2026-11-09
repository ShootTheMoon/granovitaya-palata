# -*- coding: utf-8 -*-
"""크렘린 궁전·관청 — 대크렘린궁 · 상원궁 · 무기고 · 오루제이나야 · 국립크렘린궁.

**외접 사각형을 쓰지 않는다.** 탑과 성당은 평면이 단순해서 최소외접사각형으로
충분했지만 궁전군은 그렇지 않다. 실측해 봤다:

    대크렘린궁     172 pt  실면적 15,786 m² / 외접사각 25,624 m² = **62%**
    상원궁          72 pt  실면적 11,868 m² / 외접사각 19,062 m² = **62%**
    오루제이나야     30 pt  실면적  1,986 m² / 외접사각  3,173 m² = **63%**

상원궁은 이등변삼각형이고 무기고는 중정 있는 사다리꼴, 대크렘린궁은 L 자
복합체다. 사각 블록으로 바꾸면 형태가 통째로 틀어진다.
→ **OSM 폴리곤을 그대로 압출**한다. city._extrude 와 같은 접근이다.

⚠ 파세트궁(Грановитая палата)·테렘궁(Теремной дворец)·리즈폴로제니야 교회는
  OSM 에 개별 매핑이 없다. 전부 대크렘린궁 relation 225033 한 덩어리에 묶여
  있어서 따로 세울 수가 없다. 바르테네프 도면에서 분리해야 한다.

⚠ 대크렘린궁 폴리곤 176 × 145 m 는 **복합체 전체**다. 공표 파사드 125 m 는
  남면(모스크바 강 쪽) 한 변이므로 직접 비교하면 안 된다.
"""

import math

import bmesh

import hanok
from kremlin import dome, geo_kr, measured
from kremlin.measured import val

GROUND = 0.0
SIMPLIFY = 0.8          # m. 172 pt 짜리 폴리곤을 40~60 pt 로 줄인다


# 이름: (relation, 높이, 높이신뢰도, 층수, 지붕색, 로툰다돔)
PALACES = {
    '대크렘린궁': ('225033', 47.0, 'measured', 3, 'green_roof', None),
    '상원궁': ('1359233', 27.0, 'derived', 4, 'green_roof', 24.6),
    '무기고': ('51497', 24.0, 'measured', 2, 'green_roof', None),
    '오루제이나야 팔라타': ('1359335', 22.0, 'derived', 2, 'green_roof', None),
    '국립크렘린궁': ('3031379', 29.0, 'derived', 6, 'green_roof', None),
}


def _dp(pts, tol):
    if len(pts) < 3:
        return list(pts)
    x0, y0 = pts[0]
    x1, y1 = pts[-1]
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy)
    best, bi = -1.0, 0
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        d = (math.hypot(px - x0, py - y0) if n < 1e-9
             else abs(dy * px - dx * py + x1 * y0 - y1 * x0) / n)
        if d > best:
            best, bi = d, i
    if best <= tol:
        return [pts[0], pts[-1]]
    return _dp(pts[:bi + 1], tol)[:-1] + _dp(pts[bi:], tol)


def _offset_ring(ring, dist):
    """폴리곤을 dist 만큼 바깥으로 민다(음수면 안쪽).

    각 정점에서 **이등분선** 방향으로 민다. 변마다 따로 밀면 꺾이는 곳에
    틈이 벌어진다 — city._ribbon 이 도로에서 겪은 것과 같은 문제다.
    마이터가 튀는 것을 막으려고 배율에 상한을 둔다.
    """
    n = len(ring)
    out = []
    for i in range(n):
        p = ring[i]
        a = ring[(i - 1) % n]
        b = ring[(i + 1) % n]
        # CCW 폴리곤에서 바깥 법선은 진행 방향의 오른쪽 (dy, -dx)
        n1 = _unit((p[1] - a[1], -(p[0] - a[0])))
        n2 = _unit((b[1] - p[1], -(b[0] - p[0])))
        bx, by = n1[0] + n2[0], n1[1] + n2[1]
        L = math.hypot(bx, by)
        if L < 1e-6:
            out.append(p)
            continue
        bx, by = bx / L, by / L
        c = max(0.40, bx * n1[0] + by * n1[1])
        m = min(2.4, 1.0 / c)
        out.append((p[0] + bx * dist * m, p[1] + by * dist * m))
    return out


def _unit(v):
    L = math.hypot(v[0], v[1])
    return (0.0, 0.0) if L < 1e-9 else (v[0] / L, v[1] / L)


def _band(bm, lo, hi, z0, z1):
    """아래 폴리곤 lo, 위 폴리곤 hi 사이의 띠(옆면 + 위아래 뚜껑 없음).

    통짜 압출 대신 띠를 겹쳐 쌓아 층 사이에 그림자 선을 만든다.
    """
    n = len(lo)
    a = [bm.verts.new((p[0], p[1], z0)) for p in lo]
    b = [bm.verts.new((p[0], p[1], z1)) for p in hi]
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    return a, b


def _cap(bm, ring, z, up=True):
    vs = [bm.verts.new((p[0], p[1], z)) for p in ring]
    bm.faces.new(vs if up else list(reversed(vs)))
    return vs


def _slab(bm, cx, cy, u, nv, le, ln, z0, z1):
    """벽면 방향(u)·법선(nv) 기준 직육면체."""
    poly = [(cx - u[0] * le / 2 - nv[0] * ln / 2, cy - u[1] * le / 2 - nv[1] * ln / 2),
            (cx + u[0] * le / 2 - nv[0] * ln / 2, cy + u[1] * le / 2 - nv[1] * ln / 2),
            (cx + u[0] * le / 2 + nv[0] * ln / 2, cy + u[1] * le / 2 + nv[1] * ln / 2),
            (cx - u[0] * le / 2 + nv[0] * ln / 2, cy - u[1] * le / 2 + nv[1] * ln / 2)]
    a = [bm.verts.new((p[0], p[1], z0)) for p in poly]
    b = [bm.verts.new((p[0], p[1], z1)) for p in poly]
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    for q in range(4):
        t = (q + 1) % 4
        bm.faces.new((a[q], a[t], b[t], b[q]))


def _windows(bm, ring, z0, rows, row_h, pitch=4.2, w=1.5, h=2.6, depth=0.28,
             surround=True):
    """폴리곤 둘레를 따라 창을 놓는다.

    **불리언을 쓰지 않는다.** 벽을 뚫는 대신 파인 박스 + 내민 테두리를 놓는다 —
    화성 총안과 같은 이유다. 게임 스케일에서 구멍은 안 보이고 삼각형만 먹는다.

    처음에 파인 박스만 놓았더니 렌더에서 **대크렘린궁이 백지 벽**으로 나왔다.
    창이 벽면과 같은 평면 안에서만 파여 실루엣에 아무 그림자도 안 만든 탓이다.
    → **나리치닉(наличник)** 을 넣는다. 대크렘린궁의 정체성이 바로 이
      백석 조각 창틀이고, 17세기 양식을 재현한 것이다.
      구성: 파인 개구부 + 내민 테두리 + 위쪽 관(冠).
    """
    n = len(ring)
    cnt = 0
    for i in range(n):
        p0, p1 = ring[i], ring[(i + 1) % n]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dy)
        if L < pitch:
            continue
        u = (dx / L, dy / L)
        nv = (u[1], -u[0])            # CCW 이므로 오른쪽이 바깥
        k = max(1, int(L / pitch))
        step = L / k
        for j in range(k):
            s = step * (j + 0.5)
            bx = p0[0] + u[0] * s
            by = p0[1] + u[1] * s
            for r in range(rows):
                z = z0 + row_h * (r + 0.5)
                if surround:
                    # 테두리 — 벽 밖으로 내밀어 그림자를 만든다
                    _slab(bm, bx + nv[0] * depth * 0.45, by + nv[1] * depth * 0.45,
                          u, nv, w + 0.62, depth * 0.9, z - 0.24, z + h + 0.30)
                    # 관(冠) — 창 위 처마. 나리치닉의 실루엣을 만드는 부분
                    _slab(bm, bx + nv[0] * depth * 0.72, by + nv[1] * depth * 0.72,
                          u, nv, w + 0.95, depth * 1.1,
                          z + h + 0.30, z + h + 0.56)
                    cnt += 1
                # 개구부 — 안으로 판다
                _slab(bm, bx - nv[0] * depth * 0.55, by - nv[1] * depth * 0.55,
                      u, nv, w, depth * 1.1, z, z + h)
                cnt += 1
    return cnt


def build_one(bm, bm_roof, name, ring, h, levels, rotunda=None):
    """폴리곤 하나를 궁전으로 세운다."""
    z = GROUND
    # 1. 기단 — 본체보다 살짝 넓게
    plinth = _offset_ring(ring, 0.55)
    _cap(bm, plinth, z - 0.8, up=False)
    _band(bm, plinth, plinth, z - 0.8, z + 1.3)

    # 2. 층별 띠. 층 사이를 살짝 들이밀어 그림자 선을 만든다
    #    (통짜로 두면 흰 판자로 보인다 — fortress.bm_coursed 와 같은 교훈)
    body_h = h - 1.3
    row_h = body_h / max(1, levels)
    prev = ring
    for i in range(levels):
        z0 = z + 1.3 + row_h * i
        inset = _offset_ring(ring, -0.18 if i % 2 else 0.0)
        _band(bm, prev, inset, z0, z0 + 0.25)
        _band(bm, inset, inset, z0 + 0.25, z0 + row_h)
        prev = inset

    # 3. 코니스 + 지붕
    #
    # 처음에 지붕을 **평평한 판 한 장**으로 얹었더니 렌더에서 청록 판때기로
    # 보였다. 실루엣에 아무것도 안 만든다. 안쪽으로 밀어 올린 모임지붕으로
    # 바꾼다 — 물매가 생겨야 하늘과의 경계선이 산다.
    #
    # ⚠ 오목한 폴리곤(대크렘린궁은 L 자)을 안쪽으로 크게 밀면 자기교차한다.
    #   밀어내는 양을 3 m 이내로 묶고 대신 **높이로 물매를 만든다.**
    top = z + 1.3 + body_h
    cor = _offset_ring(ring, 0.75)
    _band(bm, prev, cor, top, top + 0.55)
    _band(bm, cor, cor, top + 0.55, top + 0.9)

    roof_h = max(2.5, min(6.5, h * 0.13))
    zr = top + 0.9
    prevr, z_cur = cor, zr
    for off, f in ((-1.1, 0.52), (-2.8, 1.0)):
        r = _offset_ring(ring, off)
        z_next = zr + roof_h * f
        _band(bm_roof, prevr, r, z_cur, z_next)
        prevr, z_cur = r, z_next
    _cap(bm_roof, prevr, z_cur, up=True)

    # 4. 창
    n_win = _windows(bm, ring, z + 1.3, levels, row_h)

    # 5. 로툰다 돔 (상원궁 녹색 돔). 양파돔이 아니라 고전주의 반구다
    if rotunda:
        cx = sum(p[0] for p in ring) / len(ring)
        cy = sum(p[1] for p in ring) / len(ring)
        r = rotunda / 2.0
        dome.drum(bm, cx, cy, top + 0.9, r, r * 0.55, seg=24)
        prof = []
        for i in range(11):
            a = math.pi * 0.5 * i / 10
            prof.append((r * math.cos(a), r * 0.62 * math.sin(a)))
        dome._revolve(bm_roof, cx, cy, top + 0.9 + r * 0.55, prof, 24)
        # 정상부 국기 게양대
        dome._revolve(bm, cx, cy, top + 0.9 + r * 0.55 + r * 0.62,
                      [(0.30, 0.0), (0.14, r * 0.55)], 8)
    return n_win


def build(coll=None, osm=None):
    coll = coll or hanok.new_collection("크렘린_궁전")
    osm = osm or geo_kr.Osm()
    bm = bmesh.new()
    bm_roof = bmesh.new()
    st = {'built': 0, 'windows': 0, 'pts': {}, 'err': [], 'missing': []}

    for name, (rid, h, conf, levels, roofmat, rot) in PALACES.items():
        f = osm.by_id(rid, "relation") or osm.by_id(rid, "way")
        if f is None:
            st['missing'].append(name)
            continue
        rings = osm.rings(f)
        if not rings:
            st['missing'].append(name)
            continue
        ring = geo_kr.project(max(rings, key=lambda r: abs(geo_kr.poly_area(r))))
        # 감김을 반시계로. 법선이 뒤집히면 창이 벽 안쪽으로 파인다
        if geo_kr.poly_area(ring) < 0:
            ring.reverse()
        ring = _dp(ring, SIMPLIFY)
        if len(ring) > 1 and ring[0] == ring[-1]:
            ring = ring[:-1]
        st['pts'][name] = len(ring)
        try:
            st['windows'] += build_one(bm, bm_roof, name, ring, h, levels, rot)
            st['built'] += 1
        except Exception as exc:                 # noqa: BLE001
            st['err'].append((name, repr(exc)))

    hanok.bm_to_object(bm, "크렘린_궁전_석조", 'whitewash', coll)
    hanok.bm_to_object(bm_roof, "크렘린_궁전_지붕", 'green_roof', coll)
    return coll, st
