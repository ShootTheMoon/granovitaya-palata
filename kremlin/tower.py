# -*- coding: utf-8 -*-
"""크렘린 탑 20기.

평면·위치·방위는 **OSM 폴리곤 실측**(measured.TOWERS), 높이는 ru.wikipedia
종합표다. 형태 문법은 하나뿐이다 — **восьмерик на четверике**
(사각 몸통 위 팔각 몸통 위 팔각뿔). 15세기에 세운 것은 몸통까지고,
지금 보이는 화려한 상부는 17세기(1620~80년대)에 얹은 것이다.

계열 6가지
    gate     문탑. 몸통 + 여장 + 팔각 2단 + 텐트 + 별.
             Спасская(시계) · Никольская · Троицкая
    stepped  계단식. 사각 4단이 줄어들며 올라간다. Боровицкая 하나뿐
    round    원통. Водовзводная · Беклемишевская · Угловая Арсенальная
    plain    성벽탑. 몸통 + 여장 + 텐트. 12기로 가장 많다
    tsar     Царская. 성벽 위 4기둥 정자 + 텐트. 1680년대, 가장 늦다
    kutafya  성 밖 유일한 외곽 방어탑(отводная стрельница). 텐트가 없다

⚠ 층 비율은 전부 **derived** 다. 공개된 것은 총 높이뿐이고 층별 치수는
  어느 문헌에도 없다. 사진 비례로 잡았고, 바르테네프 도면으로 고칠 것.

⚠ 높이 기준면이 탑마다 다르다. Троицкая 80 m 는 알렉산드로프 정원(저지대)
  쪽에서 잰 값이다. measured.TOWERS 의 datum 열이 그것을 표시하고,
  여기서 DATUM_DROP 만큼 기부를 내려 실루엣을 맞춘다.
"""

import math

import bmesh

import hanok
from kremlin import dome, measured, wall
from kremlin.measured import val

# 기준면 차이. ⚠ derived — 실측이 아니다.
# 크렘린 내부 지면(보로비츠키 언덕 위)과 성 밖 저지대의 고도차. 강변·
# 알렉산드로프 정원 쪽이 낮다. 조사에서 확인한 언덕 고도차 20~25 m 중
# 성벽 발치까지의 몫만 잡은 값이다.
DATUM_DROP = {
    'kremlin': 0.0,
    'outside': 6.0,
    'wall': None,        # 성벽 윗면. wall.height_at 로 그 자리에서 잰다
}

# 계열별 층 비율 (총 높이에 대한 분율). 합이 1.0 이어야 한다.
#   body   몸통(четверик 또는 원통)
#   crown  몸통 상단 여장 + 처마
#   tiers  팔각 층 (восьмерик)
#   tent   텐트지붕 (шатёр)
#   finial 소구 + 첨탑, 또는 별
PROPORTION = {
    'gate':    dict(body=0.44, crown=0.055, tiers=0.235, tent=0.215, finial=0.055),
    'stepped': dict(body=0.30, crown=0.040, tiers=0.400, tent=0.205, finial=0.055),
    'round':   dict(body=0.56, crown=0.060, tiers=0.090, tent=0.235, finial=0.055),
    'plain':   dict(body=0.60, crown=0.065, tiers=0.000, tent=0.280, finial=0.055),
    'tsar':    dict(body=0.34, crown=0.000, tiers=0.180, tent=0.400, finial=0.080),
    'kutafya': dict(body=0.78, crown=0.220, tiers=0.000, tent=0.000, finial=0.000),
}

GATE = ('Спасская', 'Никольская', 'Троицкая')
STEPPED = ('Боровицкая',)


def kind_of(name, spec):
    if name in GATE:
        return 'gate'
    if name in STEPPED:
        return 'stepped'
    if name == 'Царская':
        return 'tsar'
    if name == 'Кутафья':
        return 'kutafya'
    if spec['shape'] == 'round':
        return 'round'
    return 'plain'


# ---------------------------------------------------------------- 지오메트리


def _rect(cx, cy, w, d, yaw, shrink=0.0):
    """중심·크기·방위로 사각형 네 꼭짓점. shrink 는 각 변에서 들어가는 양."""
    c, s = math.cos(yaw), math.sin(yaw)
    hw = max(0.2, w / 2.0 - shrink)
    hd = max(0.2, d / 2.0 - shrink)
    out = []
    for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        u, v = su * hw, sv * hd
        out.append((cx + u * c - v * s, cy + u * s + v * c))
    return out


def _prism(bm, lo, hi, z0, z1):
    """아래 폴리곤 lo → 위 폴리곤 hi 를 잇는 프리즘. 정점 수가 같아야 한다."""
    n = len(lo)
    a = [bm.verts.new((p[0], p[1], z0)) for p in lo]
    b = [bm.verts.new((p[0], p[1], z1)) for p in hi]
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    return a, b


def _coursed_body(bm, cx, cy, w, d, yaw, z0, h, batter, course=0.85, inset=0.13):
    """켜쌓기 몸통. 켜마다 번갈아 들이밀어 그림자 선을 만든다.

    통짜 박스로 두면 아무리 커도 흰 판자로 보인다 — 화성에서 겪은 그대로다.
    들이밈은 13 cm 이상이어야 50 m 거리에서 읽힌다.
    """
    nc = max(2, int(round(h / course)))
    ch = h / nc
    for k in range(nc):
        f0, f1 = k / float(nc), (k + 1) / float(nc)
        d0 = inset if (k % 2) else 0.0
        lo = _rect(cx, cy, w, d, yaw, batter * f0 + d0)
        hi = _rect(cx, cy, w, d, yaw, batter * f1 + d0)
        _prism(bm, lo, hi, z0 + h * f0, z0 + h * f1)
    return _rect(cx, cy, w, d, yaw, batter)


def _poly_perimeter(poly):
    n = len(poly)
    return sum(math.hypot(poly[(i + 1) % n][0] - poly[i][0],
                          poly[(i + 1) % n][1] - poly[i][1]) for i in range(n))


def _merlon_ring(bm, poly, z0, scale=0.62):
    """폴리곤 둘레를 따라 제비꼬리 여장을 두른다.

    성벽 여장과 같은 프로파일을 축소해서 쓴다 — 탑 여장이 성벽 여장과
    다른 형태였다면 그게 오히려 이상하다(같은 시기, 같은 이탈리아 장인).
    """
    W, H, hsh, pl, pr = wall.merlon_profile()
    W, H, hsh = W * scale, H * scale, hsh * scale
    pl = [(u * scale, z * scale) for u, z in pl]
    pr = [(u * scale, z * scale) for u, z in pr]
    mt = 0.5 * (val(measured.MERLON, 'thick_min')
                + val(measured.MERLON, 'thick_max')) * scale
    n = len(poly)
    cnt = 0
    for i in range(n):
        p0, p1 = poly[i], poly[(i + 1) % n]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dy)
        if L < W:
            continue
        u = (dx / L, dy / L)
        v = (-u[1], u[0])
        k = max(1, int(L / (W * 1.30)))
        step = L / k
        for j in range(k):
            s = step * (j + 0.5)
            cx = p0[0] + u[0] * s - v[0] * mt * 0.5
            cy = p0[1] + u[1] * s - v[1] * mt * 0.5
            wall._obox(bm, (cx, cy, z0 + hsh / 2.0), v, u, mt, W, hsh)
            wall._quad_prism(bm, pl, (cx, cy, z0), v, u, mt)
            wall._quad_prism(bm, pr, (cx, cy, z0), v, u, mt)
            cnt += 1
    return cnt


def _octagon(cx, cy, r, yaw=0.0):
    return [(cx + r * math.cos(yaw + math.pi / 8.0 + math.pi * k / 4.0),
             cy + r * math.sin(yaw + math.pi / 8.0 + math.pi * k / 4.0))
            for k in range(8)]


# ---------------------------------------------------------------- 탑 조립


def build_one(bm, name, spec, ground=0.0, bm_roof=None, bm_gold=None,
              bm_ruby=None):
    """탑 하나를 굽는다. (총고, 여장 수) 반환.

    **재질별로 bmesh 를 나눈다.** 오버데어 MeshPart 는 텍스처를 하나만 받고,
    익스포터도 오브젝트당 머티리얼 하나를 전제한다. 벽돌 몸통에 텐트지붕과
    별을 같이 구우면 전부 벽돌색이 된다 — 처음에 그렇게 나왔다.
      bm        벽돌 석조
      bm_roof   텐트지붕 (짙은 녹색 금속)
      bm_gold   소구·첨탑 (금박)
      bm_ruby   루비 별
    """
    bm_roof = bm if bm_roof is None else bm_roof
    bm_gold = bm if bm_gold is None else bm_gold
    bm_ruby = bm if bm_ruby is None else bm_ruby
    k = kind_of(name, spec)
    P = PROPORTION[k]
    H = spec['height']
    x, y = spec['x'], spec['y']
    yaw = math.radians(spec['yaw'])
    w, d = spec['w'], spec['d']
    r = 0.5 * (w + d) / 2.0                # 원형탑 반경
    z = ground
    n_mer = 0

    h_body = H * P['body']
    h_crown = H * P['crown']
    h_tiers = H * P['tiers']
    h_tent = H * P['tent']
    h_fin = H * P['finial']

    # --- 1. 몸통
    if k == 'round':
        prof = [(r, 0.0), (r * 0.93, h_body)]
        dome._revolve(bm, x, y, z, prof, 20)
        top_poly = [(x + r * 0.93 * math.cos(2 * math.pi * i / 20),
                     y + r * 0.93 * math.sin(2 * math.pi * i / 20))
                    for i in range(20)]
        rt = r * 0.93
    elif k == 'stepped':
        # 계단식 피라미드 — 사각 4단이 줄어들며 올라간다. Боровицкая 의 특징
        z1 = z
        sw, sd = w, d
        for i in range(4):
            hh = h_body / 4.0 if i == 0 else h_tiers / 3.0
            _coursed_body(bm, x, y, sw, sd, yaw, z1, hh, batter=0.18)
            z1 += hh
            sw, sd = sw * 0.78, sd * 0.78
        top_poly = _rect(x, y, sw, sd, yaw)
        rt = 0.5 * (sw + sd) / 2.0
        z = z1 - h_tiers - h_body   # 아래에서 다시 더하므로 되돌린다
        h_body = z1 - z - h_tiers
    elif k == 'tsar':
        # 성벽 위 정자 — 기둥 4개
        for px, py in _rect(x, y, w * 0.72, d * 0.72, yaw):
            dome._revolve(bm, px, py, z, [(0.28, 0.0), (0.26, h_body)], 8)
        top_poly = _rect(x, y, w, d, yaw)
        rt = 0.5 * (w + d) / 2.0
    else:
        top_poly = _coursed_body(bm, x, y, w, d, yaw, z, h_body, batter=0.55)
        rt = 0.5 * (w + d) / 2.0 - 0.55

    z += h_body

    # --- 2. 상단 처마 + 여장
    if h_crown > 0.0:
        if k == 'round':
            eave = [(x + (rt + 0.55) * math.cos(2 * math.pi * i / 20),
                     y + (rt + 0.55) * math.sin(2 * math.pi * i / 20))
                    for i in range(20)]
        else:
            eave = _rect(x, y, w + 1.1, d + 1.1, yaw,
                         0.55 if k != 'kutafya' else 0.0)
        _prism(bm, eave, eave, z, z + h_crown * 0.30)
        z += h_crown * 0.30
        n_mer += _merlon_ring(bm, eave, z, scale=0.60)
        z += h_crown * 0.70

    # --- 3. 팔각 층 (восьмерик). 문탑은 2단, 원형탑은 1단
    if h_tiers > 0.0 and k in ('gate', 'round', 'tsar'):
        tiers = 2 if k == 'gate' else 1
        rr = rt * (0.80 if k == 'gate' else 0.92)
        for i in range(tiers):
            hh = h_tiers / tiers
            lo = _octagon(x, y, rr, yaw)
            hi = _octagon(x, y, rr * 0.90, yaw)
            _prism(bm, lo, hi, z, z + hh)
            # 층 사이 코코시닉 링 — 17세기 상부의 표지
            dome.kokoshnik_ring(bm, x, y, z + hh, rr * 0.92, 8,
                                rr * 0.52, hh * 0.30, depth=rr * 0.12,
                                phase=yaw + math.pi / 8.0)
            z += hh
            rr *= 0.90
        rt = rr

    # --- 4. 텐트지붕 (шатёр). 크렘린 탑 지붕은 짙은 녹색 금속이다
    if h_tent > 0.0:
        dome.tent(bm_roof, x, y, z, rt * 1.06, h_tent, sides=8, flare=0.10)
        z += h_tent

    # --- 5. 첨탑: 별이 있으면 별, 없으면 소구 + 첨탑
    if h_fin > 0.0:
        if spec['star'] and name in measured.STARS:
            span = measured.STARS[name][0]
            pole = h_fin * 0.55
            dome._revolve(bm_gold, x, y, z, [(0.22, 0.0), (0.12, pole)], 8)
            dome.star(bm_ruby, x, y, z + pole + span / 2.0, span, yaw=yaw)
            z += pole + span
        else:
            dome._revolve(bm_gold, x, y, z, [(0.30, 0.0), (0.10, h_fin * 0.75)], 8)
            dome.ball(bm_gold, x, y, z + h_fin * 0.75, h_fin * 0.16, 10)
            z += h_fin
    return z - ground, n_mer


def build(coll=None, ground=0.0, skip=()):
    """탑 20기를 세운다. (컬렉션, 통계) 반환.

    skip 에 이름을 주면 그 탑은 만들지 않는다. 같은 자리에 스케치팹 실물
    모델(`크렘린_NC_*`)을 놓을 때 절차 생성본과 겹쳐 Z 파이팅이 나기 때문이다.
    절차 생성본은 하나의 메시로 합쳐 굽기 때문에 나중에 오브젝트 단위로
    숨길 수가 없다 — 애초에 안 만드는 것이 유일한 방법이다.
    """
    coll = coll or hanok.new_collection("크렘린_탑")
    parts = {
        'stone': (bmesh.new(), "크렘린_탑_석조", 'brick_red'),
        'roof': (bmesh.new(), "크렘린_탑_지붕", 'green_roof'),
        'gold': (bmesh.new(), "크렘린_탑_금박", 'gold_dome'),
        'ruby': (bmesh.new(), "크렘린_탑_루비별", 'star_ruby'),
    }
    stats = {'towers': 0, 'merlons': 0, 'kinds': {}, 'err': [], 'stars': 0}

    for name, spec in measured.TOWERS.items():
        if name in skip:
            stats.setdefault('skipped', []).append(name)
            continue
        drop = DATUM_DROP.get(spec['datum'], 0.0)
        if drop is None:                       # 'wall' — 성벽 윗면에 얹는다
            g = wall.height_at(spec['x'], spec['y'])
        else:
            g = ground - drop
        k = kind_of(name, spec)
        try:
            h, nm = build_one(parts['stone'][0], name, spec, ground=g,
                              bm_roof=parts['roof'][0],
                              bm_gold=parts['gold'][0],
                              bm_ruby=parts['ruby'][0])
        except Exception as exc:               # noqa: BLE001
            stats['err'].append((name, repr(exc)))
            continue
        stats['towers'] += 1
        stats['merlons'] += nm
        stats['stars'] += 1 if spec['star'] else 0
        stats['kinds'][k] = stats['kinds'].get(k, 0) + 1

    for bm, nm, mat in parts.values():
        if len(bm.verts):
            hanok.bm_to_object(bm, nm, mat, coll)
        else:
            bm.free()
    return coll, stats
