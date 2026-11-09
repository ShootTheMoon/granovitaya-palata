# -*- coding: utf-8 -*-
"""크렘린 OSM 수급 · 파싱 · 투영.

hwaseong/geo.py 와 수학은 같지만 **따로 만든 이유가 두 가지** 있다.

1) **릴레이션을 파싱해야 한다.**
   hwaseong/geo.py 는 way 만 본다("릴레이션은 이 축척에서 불필요"). 크렘린은
   그게 통하지 않는다. `way["building"]` 으로 뽑으면 26~30개가 나오는데 전부
   매표소·마구간 같은 부속 건물이고, **탑 20기와 3대 성당은 하나도 안 나온다.**
   전부 멀티폴리곤 릴레이션이기 때문이다. `nwr` 로 바꾸면 47개가 나오고
   그중 26개에 height 태그가 채워져 있다. 이 차이가 프로젝트의 실측 근간이다.

2) **모듈 전역 앵커를 갈아끼우지 않는다.**
   hwaseong/geo.py 는 `_use_anchor()` 가 ANCHOR_LAT/LON 전역을 바꾼다. 화성과
   크렘린을 같은 세션에서 빌드하면 나중에 부른 쪽이 앞의 앵커를 덮어써서
   조용히 어긋난다. 여기서는 앵커를 상수로 박고 전역을 건드리지 않는다.

좌표 규약 — **지리 방위 그대로. +X = 동, +Y = 북, 단위 m.**
    화성은 -Y 가 북이다(KCISA 모델이 바깥면을 -Y 로 두고 저작됐기 때문).
    크렘린에는 그런 제약이 없고, 대조할 자료(OSM · Kremlenagrad 1:2400 ·
    Commons 평면도)가 전부 북쪽이 위인 지도다. 북을 +Y 로 두는 편이
    도면과 겹쳐 볼 때 부호를 헷갈릴 일이 없다.

앵커
    크렘린 relation 1360641 (Wikidata Q133274, UNESCO ref:whc=545)
    Nominatim 이 돌려준 **point** 55.7516212 N, 37.6181220 E
    (bbox 중점이 아니다 — 그쪽은 55.7516181, 37.6178228 로 경도가 19 m 다르다.
     2026-08-22 Nominatim 재조회로 point 값과 일치함을 확인했다.)
"""

import math
import os
import xml.etree.ElementTree as ET

# 크렘린 릴레이션 중심. Nominatim bbox 의 중점이다.
ANCHOR_LAT, ANCHOR_LON = 55.7516212, 37.6181220

# Nominatim 이 돌려준 크렘린 relation 1360641 의 bbox. 검산에 쓴다.
KREMLIN_BBOX = (55.7480273, 55.7552089, 37.6123784, 37.6232671)  # lat0,lat1,lon0,lon1

# 수급 범위. 크렘린만이면 ±420 m 로 충분하지만 붉은광장(330×70 m)과
# 성 바실리·GUM·역사박물관이 동쪽·북동쪽으로 더 나가고, 모스크바 강이
# 남쪽에 있다. 경계에 걸친 폴리곤이 잘리지 않게 넉넉히 받는다.
FETCH_S, FETCH_N = 55.7450, 55.7590
FETCH_W, FETCH_E = 37.6080, 37.6290

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "osm", "kremlin.osm")

# 앵커 위도에서의 도 길이. WGS84 타원체에서 곡률반경으로 직접 낸다.
#
# ⚠ 예전에는 110540 / 111320·cos φ 라는 구면 근사 상수를 썼고 주석에
#   「반경 800 m 범위에서 등거리 근사 오차는 cm 급이라 무시한다」고 적혀
#   있었다. **그 진단이 틀렸다.** 오차는 등거리 근사에서 온 게 아니라
#   도 길이 상수 자체가 틀려서 생기고, 거리에 비례해 커진다:
#     110540      vs 111337.3  →  위도 -0.716%
#     62648.8     vs  62792.3  →  경도 -0.229%
#   2026-08-22 GIS 검증에서 Nominatim 실측 좌표 + Vincenty 측지선으로
#   7개 구간을 재니 씬이 실제보다 평균 0.433% 작았고, **남북 구간일수록
#   오차가 컸다**(-0.28% ~ -0.71%). 이방성이라 원인이 상수임이 확정됐다.
#   아래 값으로 바꾸면 같은 7개 구간이 전부 0.000% 가 된다.
#   자세한 것은 작업로그.md 참조.
#
# 등거리(평면) 근사 자체는 그대로 둔다 — 반경 800 m 에서 그 오차는 실제로
# mm 급이다. 문제였던 것은 근사가 아니라 상수였다.
_WGS84_A = 6378137.0
_WGS84_F = 1.0 / 298.257223563
_E2 = _WGS84_F * (2.0 - _WGS84_F)
_PHI = math.radians(ANCHOR_LAT)
_W = math.sqrt(1.0 - _E2 * math.sin(_PHI) ** 2)

# 자오선 곡률반경 M, 묘유선 곡률반경 N
M_PER_DEG_LAT = math.radians(1.0) * _WGS84_A * (1.0 - _E2) / _W ** 3   # 111337.3
M_PER_DEG_LON = math.radians(1.0) * _WGS84_A / _W * math.cos(_PHI)     # 62792.3

# 구 상수로 지어 둔 씬을 옮길 때 쓰는 일회성 보정 배율. 원점이 앵커라
# 원점 기준 이방 스케일 한 번이면 된다 (Z 는 투영과 무관하므로 1).
LEGACY_FIX = (M_PER_DEG_LON / (111320.0 * math.cos(_PHI)),   # X x1.002290
              M_PER_DEG_LAT / 110540.0,                       # Y x1.007213
              1.0)

# ⚠ WALL_WAYS 는 **삭제했다.** 「성벽을 이루는 way 4개」라고 적혀 있었지만
#   (93803735 · 185298684 · 228118828 · 1213525445) 캐시에서 넷 다 노드가
#   2개뿐이고 길이가 0.2 ~ 1.4 m, 합쳐 2.4 m 짜리 조각이다. 크렘린 성벽이
#   아니다. 캐시 안의 historic=citywalls way 는 전부 «Китайгородская стена»
#   (키타이고로드 성벽)로, 이것도 다른 벽이다.
#   어차피 이 상수를 참조하는 코드가 없었다 — 실제 성벽 중심선은
#   `wall.wall_path()` 가 **relation 1360641 의 최대 링**에서 뽑는다.
#   되살리려면 거기서부터 출발해야 한다.

# 공표 둘레. 검산 기준 — ru/en 위키 전 출처가 일치한다.
#
# ⚠ 이 값과의 일치도를 근거로 투영을 판단하지 마라. 2026-08-22 상수 보정 전에는
#   `wall.wall_path()` 의 kept_len 이 2247.7 m (+0.57%) 로 잘 맞는 것처럼
#   보였지만, 그건 **틀린 상수 두 개가 맞물린 우연**이었다. 보정 후에는
#   2279.4 m (+1.99%) 다. 2235 는 출처가 불분명한 반올림값이고, 탑 걷어내기
#   (TOWER_CUT) 근사도 섞여 있어 이 정도 차이는 정상이다.
#   투영의 근거는 Nominatim 실측 좌표 + Vincenty 측지선 7개 구간이며
#   그쪽은 0.000% 다. 작업로그.md 참조.
WALL_PERIMETER_M = 2235.0


# ------------------------------------------------------------------ 수급

OVERPASS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)

# `out geom;` 이 핵심이다. 릴레이션 멤버의 좌표가 인라인으로 따라와서
# 별도 노드 조회 없이 폴리곤을 만들 수 있다. `out body;` 로 받으면 멤버가
# ref 번호만 들고 오고, 그 way 들은 bbox 밖이면 응답에 없어서 구멍이 난다.
QUERY = """[out:xml][timeout:180];
(
  nwr["building"](%(s).7f,%(w).7f,%(n).7f,%(e).7f);
  nwr["man_made"="tower"](%(s).7f,%(w).7f,%(n).7f,%(e).7f);
  nwr["historic"](%(s).7f,%(w).7f,%(n).7f,%(e).7f);
  way["barrier"](%(s).7f,%(w).7f,%(n).7f,%(e).7f);
  way["highway"](%(s).7f,%(w).7f,%(n).7f,%(e).7f);
  nwr["place"~"square"](%(s).7f,%(w).7f,%(n).7f,%(e).7f);
  nwr["natural"="water"](%(s).7f,%(w).7f,%(n).7f,%(e).7f);
  nwr["waterway"](%(s).7f,%(w).7f,%(n).7f,%(e).7f);
  nwr["leisure"="park"](%(s).7f,%(w).7f,%(n).7f,%(e).7f);
);
out geom;
"""


def query_text():
    return QUERY % {"s": FETCH_S, "w": FETCH_W, "n": FETCH_N, "e": FETCH_E}


def fetch(force=False, path=None):
    """OSM XML 을 받아 캐시한다. 캐시가 있으면 네트워크를 타지 않는다.

    빌드가 네트워크에 의존하면 재현이 안 된다 — 화성 때 Overpass 가 혼잡해서
    막힌 적이 있고, 이번 조사에서도 메인 엔드포인트가 429 를 뱉었다.
    캐시 파일은 저장소에 함께 둔다.

    Overpass 를 쓰는 것이 hwaseong/geo.py 와 다른 점이다. 거기서는
    api.openstreetmap.org/api/0.6/map?bbox= 를 썼는데, 그 엔드포인트는
    **크렘린 범위(남북 약 1.4 km)에서 HTTP 400 을 낸다** — 노드 상한이다.
    실측해 보니 500 m 각까지만 통과했다. 게다가 릴레이션 지오메트리를
    인라인으로 주지 않아 어차피 여기 목적에는 맞지 않는다.
    """
    path = path or CACHE
    if os.path.exists(path) and not force:
        return path
    import urllib.error
    import urllib.parse
    import urllib.request

    data = urllib.parse.urlencode({"data": query_text()}).encode("utf-8")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    last = None
    for base in OVERPASS:
        try:
            req = urllib.request.Request(
                base, data=data,
                headers={"User-Agent": "kremlin-map-builder/1.0"})
            with urllib.request.urlopen(req, timeout=300) as f:
                body = f.read()
            # Overpass 는 과부하일 때 200 에 에러 XML 을 실어 보내기도 한다.
            if b"<osm" not in body[:2000]:
                raise ValueError("OSM XML 이 아니다: %r" % body[:200])
            with open(path, "wb") as g:
                g.write(body)
            return path
        except Exception as exc:               # noqa: BLE001 - 미러로 넘어간다
            last = exc
            print("Overpass 실패 %s: %s" % (base, exc))
    raise RuntimeError("Overpass 미러 전부 실패: %s" % last)


# ------------------------------------------------------------------ 파싱


def _ring_close(ring, tol=1e-9):
    if len(ring) > 1 and abs(ring[0][0] - ring[-1][0]) < tol \
            and abs(ring[0][1] - ring[-1][1]) < tol:
        return ring[:-1]
    return ring


def _stitch(segments):
    """끊긴 선분들을 끝점끼리 이어 폐곡선 링으로 만든다.

    멀티폴리곤 릴레이션의 outer 멤버는 여러 way 로 쪼개져 있고 방향도
    제각각이다. 순서대로 이으면 안 되고 끝점을 봐야 한다.
    """
    segs = [list(s) for s in segments if len(s) >= 2]
    rings = []
    while segs:
        cur = segs.pop(0)
        changed = True
        while changed and cur[0] != cur[-1]:
            changed = False
            for i, s in enumerate(segs):
                if s[0] == cur[-1]:
                    cur += s[1:]
                elif s[-1] == cur[-1]:
                    cur += list(reversed(s))[1:]
                elif s[-1] == cur[0]:
                    cur = s[:-1] + cur
                elif s[0] == cur[0]:
                    cur = list(reversed(s))[:-1] + cur
                else:
                    continue
                segs.pop(i)
                changed = True
                break
        rings.append(_ring_close(cur))
    return rings


class Osm(object):
    """캐시된 OSM XML 한 벌. **way 와 relation 을 같은 자격으로 다룬다.**

    features 는 way·relation 을 섞은 단일 리스트다. 크렘린에서는 탑이
    릴레이션, 매표소가 way 라서 둘을 갈라 두면 호출부가 매번 두 번 돌아야 한다.
    """

    def __init__(self, path=None):
        root = ET.parse(path or fetch()).getroot()

        self.nodes = {}
        self.node_tags = {}
        for n in root.findall("node"):
            i = n.get("id")
            self.nodes[i] = (float(n.get("lat")), float(n.get("lon")))
            t = {x.get("k"): x.get("v") for x in n.findall("tag")}
            if t:
                self.node_tags[i] = t

        self._way_coords = {}       # id -> [(lat, lon)]
        self.features = []
        for w in root.findall("way"):
            wid = w.get("id")
            pts = []
            refs = []
            for nd in w.findall("nd"):
                refs.append(nd.get("ref"))
                # out geom 이면 좌표가 인라인으로 온다. 아니면 노드에서 찾는다.
                if nd.get("lat") is not None:
                    pts.append((float(nd.get("lat")), float(nd.get("lon"))))
                elif nd.get("ref") in self.nodes:
                    pts.append(self.nodes[nd.get("ref")])
            self._way_coords[wid] = pts
            self.features.append({
                "id": wid, "kind": "way", "refs": refs, "pts": pts,
                "tags": {x.get("k"): x.get("v") for x in w.findall("tag")},
            })

        for r in root.findall("relation"):
            outer, inner = [], []
            for m in r.findall("member"):
                if m.get("type") != "way":
                    continue
                nds = m.findall("nd")
                if nds:
                    seg = [(float(x.get("lat")), float(x.get("lon"))) for x in nds]
                else:
                    seg = self._way_coords.get(m.get("ref"), [])
                if len(seg) < 2:
                    continue
                (inner if m.get("role") == "inner" else outer).append(seg)
            self.features.append({
                "id": r.get("id"), "kind": "relation",
                "outer": outer, "inner": inner,
                "tags": {x.get("k"): x.get("v") for x in r.findall("tag")},
            })

    # -- 조회 ------------------------------------------------------------

    def rings(self, feat):
        """지물의 외곽 링 목록. way 는 1개, 릴레이션은 여러 개일 수 있다."""
        if feat["kind"] == "way":
            return [_ring_close(feat["pts"])] if len(feat["pts"]) >= 3 else []
        return [r for r in _stitch(feat["outer"]) if len(r) >= 3]

    def coords(self, feat):
        """단일 폴리라인. way 전용 (성벽처럼 열린 선에 쓴다)."""
        return feat["pts"] if feat["kind"] == "way" else []

    def by_id(self, fid, kind=None):
        for f in self.features:
            if f["id"] == fid and (kind is None or f["kind"] == kind):
                return f
        return None

    def tagged(self, key, value=None):
        for f in self.features:
            v = f["tags"].get(key)
            if v is not None and (value is None or v == value):
                yield f

    def named(self, substr):
        """이름에 substr 이 들어가는 지물. 러시아어·영어 양쪽 태그를 본다."""
        for f in self.features:
            t = f["tags"]
            for k in ("name", "name:en", "name:ru", "old_name"):
                if substr in (t.get(k) or ""):
                    yield f
                    break


# ------------------------------------------------------------------ 투영


def to_en(lat, lon):
    """앵커 기준 (동쪽 m, 북쪽 m)."""
    return ((lon - ANCHOR_LON) * M_PER_DEG_LON,
            (lat - ANCHOR_LAT) * M_PER_DEG_LAT)


def to_latlon(x, y):
    return (ANCHOR_LAT + y / M_PER_DEG_LAT,
            ANCHOR_LON + x / M_PER_DEG_LON)


def project(latlons):
    """(lat, lon) 목록 → 사이트 로컬 (x, y). +X 동, +Y 북."""
    return [to_en(la, lo) for la, lo in latlons]


# ------------------------------------------------------------------ 계측


def poly_len(pts, closed=False):
    n = len(pts)
    if n < 2:
        return 0.0
    tot = 0.0
    for i in range(n - 1):
        tot += math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
    if closed:
        tot += math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1])
    return tot


def poly_area(ring):
    """신발끈 공식. 부호는 감김 방향(반시계 양수)."""
    a = 0.0
    n = len(ring)
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def centroid(ring):
    """폴리곤 무게중심. 면적이 0 이면 정점 평균으로 물러선다."""
    a = poly_area(ring)
    if abs(a) < 1e-9:
        return (sum(p[0] for p in ring) / len(ring),
                sum(p[1] for p in ring) / len(ring))
    cx = cy = 0.0
    n = len(ring)
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        cr = x0 * y1 - x1 * y0
        cx += (x0 + x1) * cr
        cy += (y0 + y1) * cr
    return (cx / (6.0 * a), cy / (6.0 * a))


def principal_angle(ring):
    """폴리곤의 주축 각(도). 탑 평면의 방위를 잰다.

    가장 긴 변으로 재는 방법(city._principal)은 탑처럼 변이 짧고 개수가 많은
    도형에서 불안정하다. 최소 면적 외접 사각형(rotating calipers 의 간이판)
    으로 잡는다 — 0~90도를 1도씩 훑어 넓이가 최소인 각을 고른다.
    """
    best, best_a = 0.0, None
    for deg in range(90):
        r = math.radians(deg)
        c, s = math.cos(r), math.sin(r)
        xs = [p[0] * c + p[1] * s for p in ring]
        ys = [-p[0] * s + p[1] * c for p in ring]
        a = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if best_a is None or a < best_a:
            best, best_a = float(deg), a
    return best


def oriented_extent(ring, deg=None):
    """(폭, 깊이, 각도). 각도를 주지 않으면 principal_angle 로 잡는다.

    탑 20기의 평면 치수는 어느 공개 출처에도 없다 — OSM 폴리곤에서 재는 것이
    유일한 길이다. 그래서 '외접 사각형'이 곧 실측치가 된다.
    """
    if deg is None:
        deg = principal_angle(ring)
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    xs = [p[0] * c + p[1] * s for p in ring]
    ys = [-p[0] * s + p[1] * c for p in ring]
    return (max(xs) - min(xs), max(ys) - min(ys), deg)


def circularity(ring):
    """4πA/P² — 1.0 이면 완전한 원, 정사각형은 약 0.785.

    크렘린 탑에는 원형(Водовзводная·Беклемишевская·Угловая Арсенальная)과
    사각형이 섞여 있다. OSM 폴리곤만 보고 어느 쪽인지 갈라야 해서 쓴다.
    """
    p = poly_len(ring, closed=True)
    if p <= 0:
        return 0.0
    return 4.0 * math.pi * abs(poly_area(ring)) / (p * p)


def load(path=None):
    """(osm, 안내문). 호출부는 이것만 쓰면 된다."""
    o = Osm(path or fetch())
    return o
