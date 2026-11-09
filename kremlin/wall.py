# -*- coding: utf-8 -*-
"""크렘린 성벽 + 제비꼬리 여장.

경로
    OSM castle relation 1360641 폴리곤(1204 pt, 둘레 2570.6 m)에서
    **탑 20기의 돌출부를 걷어낸** 선이 성벽 중심선이다. 크렘린 성벽은 탑과 탑
    사이가 곡선 없이 직선이라(화성과 다른 점) 걷어낸 자리는 직선 현으로 이으면 된다.
    걷어내고 재면 2296.7 m 로 공표 2235 m 와 2.8% 차이다 — 두 숫자가 이렇게
    맞는다는 것이 '공표값 = 탑 제외 순수 성벽 길이'라는 근거이고,
    여장 1045개를 이 길이에 걸어야 하는 이유다.

켜쌓기
    fortress.bm_coursed 는 축정렬 박스만 만든다. 성벽은 방향이 제각각이라
    그대로 못 쓴다. 대신 **켜 하나를 구간 전체에 걸친 긴 프리즘 한 개**로
    만든다. 돌 하나씩 놓으면 2.3 km × 19켜 = 삼각형이 수십만이 되는데,
    켜 단위 프리즘이면 켜마다 12 삼각형이라 전체가 1만 이하로 떨어진다.
    그림자 선을 만드는 것은 돌의 개수가 아니라 **켜의 들이밈**이므로
    보이는 결과는 같다. 화성 주석의 교훈 그대로 들이밈은 넉넉히 준다 —
    5 cm 로는 50 m 거리에서 그림자가 안 잡혀 벽이 흰 판자로 보였다.

여장
    제비꼬리(зубцы «ласточкин хвост»). 이탈리아 기벨린식 메를론이고,
    성벽을 지은 것이 이탈리아 건축가들이라 그대로 건너왔다.
    **불리언을 쓰지 않는다.** V 홈은 파는 게 아니라 몸통 박스 + 좌우 뿔
    사다리꼴 프리즘 3조각으로 쌓는다. 세 조각 전부 볼록이라 n-gon 삼각화가
    엉킬 일이 없다 — 오목 7각형 프로파일 하나로 만들면 익스포트 삼각화에서
    면이 뒤집힌다.
"""

import math

import bmesh

import hanok
from kremlin import geo_kr, measured
from kremlin.measured import val

# ---------------------------------------------------------------- 경로 추출

# 탑 중심에서 이 배수 안쪽의 폴리곤 점은 탑 돌출부로 보고 걷어낸다.
# 1.0 이면 외접원인데 그러면 탑에 붙은 성벽 시작점까지 먹어서 현이 안쪽으로
# 파고든다. 0.62 는 탑 폭의 62% — 사각탑이면 대략 변의 중앙까지다.
TOWER_CUT = 0.62
TOWER_CUT_PAD = 1.2         # m. 위에 더 얹는 여유

SIMPLIFY_TOL = 1.4          # m. Douglas-Peucker. 1204 pt → 40~60 pt 로 줄인다


def _dp(pts, tol):
    """Douglas-Peucker. 곡선 노이즈를 걷고 직선 구간을 살린다."""
    if len(pts) < 3:
        return list(pts)
    x0, y0 = pts[0]
    x1, y1 = pts[-1]
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy)
    best, bi = -1.0, 0
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        if n < 1e-9:
            d = math.hypot(px - x0, py - y0)
        else:
            d = abs(dy * px - dx * py + x1 * y0 - y1 * x0) / n
        if d > best:
            best, bi = d, i
    if best <= tol:
        return [pts[0], pts[-1]]
    return _dp(pts[:bi + 1], tol)[:-1] + _dp(pts[bi:], tol)


def wall_path(osm=None, simplify=SIMPLIFY_TOL):
    """성벽 중심선 (닫힌 폴리라인). 반시계 감김으로 정규화해서 돌려준다.

    반환 (path, info) — info 는 검산용 dict.
    """
    osm = osm or geo_kr.Osm()
    kr = osm.by_id("1360641", "relation")
    ring = geo_kr.project(
        max(osm.rings(kr), key=lambda r: abs(geo_kr.poly_area(r))))

    # 탑 걷어내기. Кутафья 는 성벽에서 100 m 넘게 떨어져 있어 영향이 없다.
    cuts = []
    for nm, t in measured.TOWERS.items():
        r = max(t['w'], t['d']) * TOWER_CUT + TOWER_CUT_PAD
        cuts.append((t['x'], t['y'], r * r))
    kept = [p for p in ring
            if not any((p[0] - cx) ** 2 + (p[1] - cy) ** 2 < rr
                       for cx, cy, rr in cuts)]

    # 감김을 반시계로 통일한다. 법선이 뒤집히면 벽 바깥면이 안으로 향한다 —
    # 익스포터 preflight 가 미러로 잡는 것과 같은 종류의 사고다.
    if geo_kr.poly_area(kept) < 0:
        kept.reverse()

    path = _dp(kept, simplify) if simplify else kept
    if len(path) > 1 and path[0] == path[-1]:
        path = path[:-1]

    info = {
        'ring_pts': len(ring),
        'ring_len': geo_kr.poly_len(ring, closed=True),
        'kept_pts': len(kept),
        'kept_len': geo_kr.poly_len(kept, closed=True),
        'path_pts': len(path),
        'path_len': geo_kr.poly_len(path, closed=True),
    }
    return path, info


# ---------------------------------------------------------------- 높이 프로파일
#
# ⚠ **derived 다.** 공표값은 「5 ~ 19 m, 강변이 낮고 붉은광장 쪽이 높다」뿐이고
#   구간별 실측치는 공개돼 있지 않다. 방위별 제어점으로 부드럽게 잇는다.
#   Commons Category:Moscow Kremlin Wall(253파일)로 대조해 고칠 것.
#
#   방위는 폴리곤 무게중심에서 본 각(도). +X(동)=0, 반시계.
HEIGHT_BY_BEARING = [
    (-90.0, 8.0),      # 남 — 모스크바 강변. 보로비츠키 언덕 벼랑 위라 낮다
    (0.0, 17.5),       # 동 — 붉은광장. 해자가 있던 쪽이라 가장 높다
    (90.0, 15.5),      # 북 — 알렉산드로프 정원 북단
    (180.0, 13.5),     # 서 — 알렉산드로프 정원
]


def height_at(x, y, cx=0.0, cy=0.0):
    """위치 → 성벽 높이(m). 방위 제어점 4개를 코사인 보간한다."""
    b = math.degrees(math.atan2(y - cy, x - cx))
    pts = sorted((bb % 360.0, h) for bb, h in HEIGHT_BY_BEARING)
    b %= 360.0
    for i in range(len(pts)):
        b0, h0 = pts[i]
        b1, h1 = pts[(i + 1) % len(pts)]
        span = (b1 - b0) % 360.0
        off = (b - b0) % 360.0
        if off <= span or i == len(pts) - 1:
            t = off / span if span > 1e-9 else 0.0
            t = 0.5 - 0.5 * math.cos(math.pi * min(t, 1.0))   # 코사인 이징
            return h0 + (h1 - h0) * t
    return pts[0][1]


def _outer_shift(t, own_w, batter=0.30):
    """중심선 기준으로 얼마나 바깥(-v)으로 밀어야 바깥면에 붙는가.

    성벽 몸체는 중심선을 끼고 대칭으로 서고 위로 갈수록 batter 만큼 좁아진다.
    윗면 두께는 t − 2·batter 이므로, 폭 own_w 짜리 부재를 그 바깥 모서리에
    맞추려면 (윗면두께 − own_w)/2 만큼 민다.
    """
    t_top = max(own_w, t - 2.0 * batter)
    return (t_top - own_w) / 2.0


def thick_at(h):
    """높이 → 두께. 낮은 구간이 두껍다(강변 방어). 3.5 ~ 6.5 m."""
    t0 = val(measured.WALL, 'thick_min')
    t1 = val(measured.WALL, 'thick_max')
    h0 = val(measured.WALL, 'height_min')
    h1 = val(measured.WALL, 'height_max')
    u = (h - h0) / max(1e-6, h1 - h0)
    return t1 + (t0 - t1) * max(0.0, min(1.0, u))


# ---------------------------------------------------------------- 지오메트리


def _obox(bm, c, u, v, su, sv, sw):
    """방향이 있는 육면체. u = 길이 방향 단위벡터, v = 폭 방향 단위벡터.

    hanok.bm_box 는 축정렬만 되므로 성벽처럼 방향이 제각각인 것에는 못 쓴다.
    """
    cx, cy, cz = c
    hu, hv, hw = su / 2.0, sv / 2.0, sw / 2.0
    vs = []
    for sz in (-hw, hw):
        for sv_ in (-hv, hv):
            for su_ in (-hu, hu):
                vs.append(bm.verts.new((
                    cx + u[0] * su_ + v[0] * sv_,
                    cy + u[1] * su_ + v[1] * sv_,
                    cz + sz)))
    # 인덱스: 0..3 아랫면 (--, +-, -+, ++), 4..7 윗면
    q = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
         (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    for a, b, cc, d in q:
        bm.faces.new((vs[a], vs[b], vs[cc], vs[d]))
    return vs


def _seg_prism(bm, p0, p1, v, t0, t1, zb0, zt0, zb1, zt1):
    """양 끝의 높이와 두께가 다른 육면체. 성벽 켜 하나.

    _obox 로 켜를 놓으면 구간마다 높이가 상수라 **경계에서 벽 윗면이 계단처럼
    튄다.** 실제로 그렇게 나왔다(첫 렌더에서 동벽 중간에 단차가 보였다).
    양 끝을 따로 받아 윗면이 이어지게 한다.

    v 는 성벽 왼쪽 법선이고 감김이 반시계라 크렘린 **안쪽**을 가리킨다.
    따라서 -v 쪽이 성 바깥면이다.
    """
    a_o = (p0[0] - v[0] * t0 / 2.0, p0[1] - v[1] * t0 / 2.0)
    a_i = (p0[0] + v[0] * t0 / 2.0, p0[1] + v[1] * t0 / 2.0)
    b_o = (p1[0] - v[0] * t1 / 2.0, p1[1] - v[1] * t1 / 2.0)
    b_i = (p1[0] + v[0] * t1 / 2.0, p1[1] + v[1] * t1 / 2.0)
    cols = ((a_o, zb0, zt0), (b_o, zb1, zt1), (b_i, zb1, zt1), (a_i, zb0, zt0))
    V = [(bm.verts.new((p[0], p[1], zb)), bm.verts.new((p[0], p[1], zt)))
         for p, zb, zt in cols]
    bm.faces.new([V[i][1] for i in (0, 1, 2, 3)])          # 윗면
    bm.faces.new([V[i][0] for i in (3, 2, 1, 0)])          # 아랫면
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((V[i][0], V[j][0], V[j][1], V[i][1]))
    return V


def _quad_prism(bm, profile, c, u, v, length):
    """(w, z) 프로파일 다각형을 u 방향으로 length 만큼 밀어낸 프리즘.

    profile 은 **볼록**이어야 한다. 여장 뿔처럼 사다리꼴을 만들 때 쓴다.
    """
    cx, cy, cz = c
    hl = length / 2.0
    rings = []
    for s in (-hl, hl):
        ring = []
        for w, z in profile:
            ring.append(bm.verts.new((
                cx + u[0] * s + v[0] * w,
                cy + u[1] * s + v[1] * w,
                cz + z)))
        rings.append(ring)
    a, b = rings
    n = len(profile)
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    return rings


def merlon_profile():
    """제비꼬리 여장의 (폭, 높이) 프로파일 조각 3개.

    몸통 박스 + 좌우 뿔 사다리꼴. V 홈은 두 뿔의 안쪽 빗변이 만든다 —
    어깨 높이에서 폭 0, 꼭대기에서 notch_width 로 벌어진다.
    """
    W = val(measured.MERLON, 'width')
    H = val(measured.MERLON, 'height_max')
    nd = val(measured.MERLON, 'notch_depth')
    nw = val(measured.MERLON, 'notch_width')
    hs = H - nd                       # 어깨 높이 = V 꼭짓점
    hw, hnw = W / 2.0, nw / 2.0
    left = [(-hw, hs), (0.0, hs), (-hnw, H), (-hw, H)]
    right = [(hw, hs), (hw, H), (hnw, H), (0.0, hs)]
    return W, H, hs, left, right


def build(coll=None, path=None, osm=None, courses=True):
    """성벽 몸체 + 여장을 세운다. (컬렉션, 통계) 반환."""
    coll_w = coll or hanok.new_collection("크렘린_성벽")
    coll_m = hanok.new_collection("크렘린_여장")
    if path is None:
        path, _ = wall_path(osm)

    course_h = 0.78                    # fortress.bm_coursed 와 같은 켜 높이
    inset = 0.13                       # **13 cm 이상.** 화성에서 5 cm 는 안 읽혔다
    batter = 0.30                      # 위로 갈수록 좁아지는 민흘림

    bm_body = bmesh.new()
    bm_mer = bmesh.new()
    n_mer = 0
    tot_len = 0.0
    hs_seen = []

    n = len(path)
    W, H, hshoulder, prof_l, prof_r = merlon_profile()
    mt = 0.5 * (val(measured.MERLON, 'thick_min')
                + val(measured.MERLON, 'thick_max'))
    sill_t = val(measured.MERLON, 'sill_thick')

    for i in range(n):
        p0, p1 = path[i], path[(i + 1) % n]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dy)
        if L < 0.05:
            continue
        tot_len += L
        v = (-dy / L, dx / L)          # 왼쪽 법선. 감김이 반시계라 성 안쪽이다

        # 높이는 **정점마다** 잰다. 구간 중점에서 한 번만 재면 경계에서
        # 윗면이 계단처럼 튄다 — 첫 빌드에서 실제로 그렇게 나왔다.
        h0, h1 = height_at(*p0), height_at(*p1)
        t0, t1 = thick_at(h0), thick_at(h1)
        hs_seen += [h0, h1]

        # --- 몸체: 켜 하나 = 구간 전체를 지나는 긴 프리즘. 양 끝 높이가 다르다.
        if courses:
            nc = max(1, int(round(0.5 * (h0 + h1) / course_h)))
            for k in range(nc):
                f = (k + 0.5) / nc
                d = inset if (k % 2) else 0.0
                shrink = 2.0 * (batter * f + d)
                _seg_prism(bm_body, p0, p1, v,
                           max(0.4, t0 - shrink), max(0.4, t1 - shrink),
                           h0 * k / nc, h0 * (k + 1) / nc,
                           h1 * k / nc, h1 * (k + 1) / nc)
        else:
            _seg_prism(bm_body, p0, p1, v, t0, t1, 0.0, h0, 0.0, h1)

        # --- 미석: 여장 아래 연속 띠. **바깥면 쪽으로 붙인다.**
        #     여장은 성벽 두께 한가운데가 아니라 바깥 가장자리에 서고, 안쪽은
        #     전투 통로(боевой ход, 폭 2~4.5 m)로 비어 있어야 한다.
        #     처음에 중심선에 놓았더니 통로가 여장 양쪽으로 갈려 보였다.
        sw = mt + 0.22
        o0, o1 = _outer_shift(t0, sw), _outer_shift(t1, sw)
        _seg_prism(bm_body, (p0[0] - v[0] * o0, p0[1] - v[1] * o0),
                   (p1[0] - v[0] * o1, p1[1] - v[1] * o1), v,
                   sw, sw, h0, h0 + sill_t, h1, h1 + sill_t)

    # --- 여장: **닫힌 경로 전체를 호길이로 균등 분할한다.**
    #
    # 구간마다 따로 놓았더니 경계에서 간격이 흐트러지고(27군데) 개수도
    # 1021 로 24개 모자랐다. 개수 1,045 는 역사 기록이고 경로 길이는 실측이니,
    # 피치는 그 둘에서 **유도되는** 값이지 독립 파라미터가 아니다.
    n_target = val(measured.MERLON, 'count')
    cum = [0.0]
    for i in range(n):
        p0, p1 = path[i], path[(i + 1) % n]
        cum.append(cum[-1] + math.hypot(p1[0] - p0[0], p1[1] - p0[1]))
    total = cum[-1]
    step = total / n_target
    seg = 0
    for k in range(n_target):
        s = k * step
        while seg < n - 1 and cum[seg + 1] <= s:
            seg += 1
        p0, p1 = path[seg], path[(seg + 1) % n]
        L = cum[seg + 1] - cum[seg]
        if L < 1e-6:
            continue
        f = (s - cum[seg]) / L
        cx = p0[0] + (p1[0] - p0[0]) * f
        cy = p0[1] + (p1[1] - p0[1]) * f
        u = ((p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L)
        v = (-u[1], u[0])
        h = height_at(cx, cy)
        # 미석과 같은 이유로 바깥면에 붙인다
        off = _outer_shift(thick_at(h), mt)
        cx -= v[0] * off
        cy -= v[1] * off
        z0 = h + sill_t
        c = (cx, cy, z0)
        _obox(bm_mer, (cx, cy, z0 + hshoulder / 2.0), v, u, mt, W, hshoulder)
        # 좌우 뿔. 프로파일의 폭 축은 성벽 진행 방향(u)이다
        _quad_prism(bm_mer, prof_l, c, v, u, mt)
        _quad_prism(bm_mer, prof_r, c, v, u, mt)
        n_mer += 1
    pitch = step

    hanok.bm_to_object(bm_body, "크렘린_성벽_벽체", 'brick_red', coll_w)
    hanok.bm_to_object(bm_mer, "크렘린_여장_제비꼬리", 'brick_red', coll_m)

    stats = {
        'segments': n,
        'length': tot_len,
        'merlons': n_mer,
        'merlon_target': val(measured.MERLON, 'count'),
        'h_min': min(hs_seen) if hs_seen else 0.0,
        'h_max': max(hs_seen) if hs_seen else 0.0,
    }
    return coll_w, stats
