# -*- coding: utf-8 -*-
"""궁궐 사이트 레지스트리.

bpy 에 의존하지 않는다 — 헤드리스에서도, 익스포터에서도 그대로 import 한다.

**왜 필요한가**
`hanok.new_collection` 은 같은 이름이면 기존 컬렉션을 조용히 돌려준다.
궁궐이 둘 이상이면 이름이 겹치는 순간 두 궁궐의 부재가 한 컬렉션에 섞이고,
익스포터의 `group_of` 는 컬렉션 이름으로 그룹을 정하므로 **덕수궁 회랑이
경복궁 그룹으로 분류되는** 조용한 오분류가 난다.

여기서 컬렉션 이름을 한 곳에 모아 두고, 모듈을 읽는 시점에 중복을 막는다.
빌더 쪽에는 인자를 새로 흘리지 않는다 — 익스포터가 어차피 컬렉션 이름과
객체 이름만 보기 때문에, 인자를 추가해도 얻는 게 없다.
"""

# ------------------------------------------------------------------ 경복궁

GBG = {
    "code": "GBG",
    "name": "경복궁",
    # 컬렉션 이름 → 익스포트 그룹 코드
    "collections": {
        "근정전": "GJJ",
        "사정전": "SJJ",
        "조정": "CYD",
        "유물": "ART",
    },
    # 한 컬렉션 안에서 이름 접두사로 다시 갈리는 경우.
    # 순서가 의미를 갖는다 — export_overdare.group_of 의 if 사슬과 동일한 순서.
    "name_rules": [
        ("회랑_담장", [
            ("근정문", "GJM"),
            ("사정문", "SJM"),
            ("담장", "WAL"),
            ("회랑_모서리", "CNR"),
            ("회랑_북", "COR_N"),
            ("회랑_남", "COR_S"),
            ("회랑_서", "COR_EW"),
            ("회랑_동", "COR_EW"),
        ], "COR_X"),
    ],
    # 네이티브 Part 로 내보낼 그룹 (순수 축정렬 박스만)
    "part_groups": {"CYD", "WAL"},
    "parent_model": "Gyeongbokgung",
    "floor_y_cm": 5000.0,
    "origin_m": (0.0, 0.0, 0.0),
    "axis_deg": 0.0,
}

# ------------------------------------------------------------------ 덕수궁

DSG = {
    "code": "DSG",
    "name": "덕수궁",
    "collections": {
        "덕수궁_중화전": "JHJ",
        "덕수궁_중화문": "JHM",
        "덕수궁_석어당": "SED",
        "덕수궁_준명당": "JMD",
        "덕수궁_즉조당": "JJD",
        "덕수궁_복도각": "BDG",
        "덕수궁_대한문": "DHM",
        "덕수궁_마당": "DYD",
    },
    "name_rules": [],
    "part_groups": {"DYD"},
    "parent_model": "Deoksugung",
    "floor_y_cm": 5000.0,
    # 오버데어 배치는 나중에 정한다. 경복궁과 겹치지 않게만 띄워 둔다.
    "origin_m": (600.0, 0.0, 0.0),
    # 덕수궁 주축은 정북이 아니다 — 중화문→중화전이 방위각 11.7도.
    # 유도: R_z(θ)·(0,1,0) = (−sinθ, cosθ, 0). +V 가 북에서 동으로 11.7도
    #       기울려면 −sinθ = +sin11.7° → θ = −11.7°.
    "axis_deg": -11.7,
    "attribution": "3D 실측모델: 국가유산청 디지털정보담당관실 (공공누리 출처표시)",
}

# ------------------------------------------------------------ 수원 화성

# 유일하게 **절차 생성이 아닌** 사이트다. 한국문화정보원(KCISA)이 정밀실측으로
# 만든 장안문 일곽 모델(스케치팹 CC BY 4.0)을 감축해서 쓴다.
# 자세한 내용은 hwaseong/heritage.py.
HSF = {
    "code": "HSF",
    "name": "수원화성",
    "collections": {
        # 장안문(북문)
        "화성_장안문": "JAM",        # 문루 목조·지붕
        "화성_성벽": "SBK",          # 육축·홍예·성벽·여장·옹성·계단
        "화성_소품": "HPR",          # 깃발·홍이포·현판·초소
        # 팔달문(남문) — KCISA 가 문루 메시를 장안문과 공유하지만, 컬렉션을
        # 섞으면 팔달문 부재가 장안문 그룹으로 분류된다. 그룹을 따로 둔다.
        "화성_팔달문": "PDM",
        "화성_팔달문_성벽": "PSB",
        "화성_팔달문_소품": "PHP",
        # 화성행궁
        "화성_우화관": "UHG",
        # 스케치팹에 스캔이 없어 의궤 계열 자료로 절차 생성한 것들
        # (hwaseong/build_uigwe.py). 재질이 팔레트 키라 material_key 단색으로
        # 칠해진다 — 스캔과 달리 텍스처가 필요 없다.
        "화성_화서문": "HSM",
        "화성_공심돈": "GSD",
        "화성_방화수류정": "BSJ",
        # OSM 실측 지오로 세운 장안문 주변 도시 (hwaseong/city.py).
        # 압출 프리즘·폴리라인 띠라 축정렬 박스가 아니다 → part_groups 에 안 넣는다.
        "화성_도시_건물": "CTB",
        "화성_도시_도로": "CTR",
        "화성_도시_소품": "CTP",   # 스케치팹 CC-BY 가로수·상가
        # 팔달문 주변 도시 (OSM way 1024560873 앵커)
        "화성_팔달도시_건물": "PTB",
        "화성_팔달도시_도로": "PTR",
        "화성_팔달도시_소품": "PTP",
        # 지면. part_groups 에 넣어 두었지만 **지금은 네이티브 Part 로 안 나간다** —
        # 지형 기복(hwaseong/dem.py)을 넣은 뒤로 12 m 격자 메시라
        # extract_boxes 가 축정렬 박스 검사에서 걸러 일반 메시로 떨어진다
        # (폴리곤 2,597 개, 6 의 배수가 아니라 첫 관문에서 None).
        # 의도된 폴백이고 5,194 삼각형뿐이라 그대로 둔다. DEM 캐시가 없어
        # 평면 폴백을 타면 다시 박스가 되어 Part 로 나간다.
        "화성_지면": "HGD",
        # 성 밖 수목·바위 (hwaseong/terrain.py 가 산포)
        "화성_수목": "VEG",
    },
    "name_rules": [],
    "part_groups": {"HGD"},
    "parent_model": "Hwaseong",
    "floor_y_cm": 5000.0,
    "origin_m": (1200.0, 0.0, 0.0),
    # 아직 실측하지 않았다 — hwaseong/layout.py 의 AXIS_DEG 주석 참조.
    "axis_deg": 0.0,
    # **CC BY 4.0 — 게임 내 크레딧 의무.** 로비 표지판이나 게임 설명란에 넣을 것.
    "attribution": "3D 모델: 한국문화정보원(KCISA), CC BY 4.0 "
                   "(스케치팹 807b2e1a414c4db4989ec1c0365dba89)",
}

# ------------------------------------------------------ 모스크바 크렘린

# 절차 생성과 스케치팹 에셋을 섞는다. 자세한 내용은 kremlin/.
#
# **NC 컬렉션은 여기에 일부러 등록하지 않는다.**
# 스파스카야(CC BY-NC-SA)·이반대제종탑(CC BY-NC-SA)·양파돔(CC BY-NC)은
# 렌더 컷에만 쓰고 오버데어로는 내보내지 않는다 — 오버데어는 UGC 게임
# 플랫폼이라 게시 자체가 비상업 조건에 걸리고, SA 는 파생물에 전염된다.
# group_of 가 site_of_collection 에 위임하므로, 레지스트리에 없는 컬렉션은
# 그룹을 못 받아 **익스포트에서 자동으로 빠진다.** 익스포터를 고칠 필요가 없다.
# 같은 대상의 절차 생성본은 아래 KTW/KBT 에 정상 등록돼 있어 그 자리를 채운다.
NC_COLLECTIONS = (
    "크렘린_NC_스파스카야",
    "크렘린_NC_종탑",
    "크렘린_NC_양파돔",
)

KRM = {
    "code": "KRM",
    "name": "모스크바크렘린",
    "collections": {
        "크렘린_성벽": "KWL",        # 켜쌓기 벽체 + 육축
        "크렘린_여장": "KMR",        # 제비꼬리 총안 1,045개
        "크렘린_탑": "KTW",          # 탑 20기 절차 생성
        "크렘린_별": "KST",          # 루비 별 5기 (스케치팹 CC BY)
        "크렘린_성당": "KCA",        # 우스펜스키·아르한겔스키·블라고베셴스키
        "크렘린_종탑": "KBT",        # 이반 대제 종탑 절차 생성본
        "크렘린_궁전": "KPL",        # 대크렘린궁·상원궁·무기고 (파세트궁은 아래 별도)
        "크렘린_파세트궁": "KGV",    # 외피 + 실내. 실내를 지은 첫 건물이다
        # 걸어다니는 면만 따로 뺀다. ⚠ 이 건물은 yaw 14° 라서 월드 축정렬이
        # 아니고, extract_boxes 는 matrix_world 를 구운 **월드 좌표**에서
        # 박스를 찾는다 → 지금 파이프라인으로는 네이티브 Part 가 안 나온다.
        # cframe 에 회전이 없는 것도 같은 제약이다. 분리해 둔 것은 나중에
        # 익스포터가 방향을 실을 수 있게 되면 바로 쓰기 위해서다.
        "크렘린_파세트궁_바닥": "KGF",
        "크렘린_광장": "KSQ",        # 성당광장 포장
        "크렘린_소품": "KPR",        # 차르대포·차르종·가로등
        "크렘린_지면": "KGD",        # 축정렬 박스라 네이티브 Part 로 나간다
        "붉은광장_포장": "RSQ",
        "붉은광장_건물": "RSB",      # GUM·역사박물관·레닌묘
        "붉은광장_성바실리": "RSV",
    },
    "name_rules": [],
    "part_groups": {"KGD"},
    "parent_model": "MoscowKremlin",
    "floor_y_cm": 5000.0,
    # 경복궁(0)·덕수궁(600)·화성(1200) 다음 자리.
    "origin_m": (1800.0, 0.0, 0.0),
    # 아직 실측하지 않았다 — kremlin/geo_kr.py 가 성벽 way 에서 잰다.
    "axis_deg": 0.0,
    "attribution": (
        "지도 데이터: © OpenStreetMap contributors (ODbL 1.0) | "
        "3D 모델(CC BY 4.0): Kremlin Star — kurgunu (482e8266fe5b41609a5567196370ff79), "
        "Saint Basil's Cathedral — Dinendra Neyo (fb52c0ba7ab24c43a9c89530be24a695), "
        "Lenin's Mausoleum (f026a3a33f7f409fa9af484f376371fc), "
        "Tsar Bell (2d2f3fdaf1b2401c84508cd6659e1c06), "
        "Kremlin Lamp — psyk3rwork (f8c3e1816ea149c5980faa222313aab5) | "
        # 렌더 전용. 컬렉션 이름이 크렘린_NC_* 라 익스포터가 건너뛴다.
        # NC 라도 **BY 의무는 그대로 남으므로** 여기 적는다.
        # 2026-08-22 Sketchfab API 로 확인: Rusych, by-nc-sa, 482,512 면.
        "3D 모델(CC BY-NC-SA 4.0, 렌더 전용 · 오버데어 미포함): "
        "Spasskaya Tower — Rusych (8fcd3fec98964693b1dec0681ba60742) | "
        "텍스처: Poly Haven · ambientCG (CC0)"
    ),
}

# ------------------------------------------------- 크렘린 파세트궁 실내
#
# 외피를 버리고 **방만** 지은 별도 씬이다 (`kremlin_interior.blend`,
# `kremlin/interior.py`). KRM 과 컬렉션·그룹이 겹치지 않아야 하므로 코드를
# 따로 둔다 — `_check()` 가 겹치면 import 시점에 터뜨린다.
#
# ★ 이 사이트의 존재 이유: **원점 축정렬**이다. KRM 의 파세트궁은 yaw 14° 라
#   `extract_boxes()` 가 월드 좌표에서 축정렬 박스를 못 찾아 바닥이 네이티브
#   Part 가 못 됐다(KGF 가 그래서 비어 있다). 실내는 yaw 0 이라 바닥·기둥·
#   다도·천장캡·콜라이더가 전부 Part 로 나간다 → 걸어 다닐 수 있다.
KGI = {
    "code": "KGI",
    "name": "파세트궁실내",
    "collections": {
        "파세트실내_벽체": "KIW",
        "파세트실내_볼트": "KIV",       # сени 횡단 리브 포함
        "파세트실내_기둥": "KIP",
        "파세트실내_바닥": "KIF",
        "파세트실내_다도": "KID",       # 벤치 겸용 — 올라설 수 있어야 한다
        "파세트실내_천장캡": "KIC",
        "파세트실내_창살": "KIG",
        "파세트실내_임포스트": "KIM",   # 볼트가 앉는 높이를 도는 띠
        # 보이지 않는 충돌 전용. MeshPart 의 convex 분해로는 벽을 뚫고 나가므로
        # 개구부 없는 통짜 박스를 따로 깐다.
        # ⚠ `export_overdare.collect_units()` 는 `hide_render` 가 켜진 것을
        #   건너뛴다. 발행 직전에 `interior.set_collider_visible(ob, True)`.
        "파세트실내_콜라이더": "KIX",
        "파세트실내_소품": "KIR",       # Hunyuan3D 생성 가구
        # 아랫층(подклет). 전부 축정렬 박스라 **메시 유닛 예산을 한 개도 안 쓰고**
        # 네이티브 Part 로만 나간다 — 콜라이더를 따로 깔 필요도 없다.
        "파세트실내_하층벽": "KJW",
        "파세트실내_하층바닥": "KJF",
        "파세트실내_하층기둥": "KJP",
        "파세트실내_계단": "KJS",
    },
    "name_rules": [],
    # 창살(KIG)은 사선 프리즘이라 축정렬 박스가 아니다 — 넣어도 조용히 메시로
    # 떨어지지만, 의도를 분명히 하려고 뺀다.
    "part_groups": {"KIF", "KIP", "KID", "KIC", "KIM", "KIX",
                    "KJW", "KJF", "KJP", "KJS"},
    "parent_model": "GranovitayaInterior",
    "floor_y_cm": 5000.0,
    # 경복궁 0 · 덕수궁 600 · 화성 1200 · 크렘린 1800 다음 자리.
    "origin_m": (2400.0, 0.0, 0.0),
    "axis_deg": 0.0,
    "attribution": (
        "치수 근거: 『Русское зодчество』 вып.2 Табл.12~15 (1953, 공유저작물) | "
        "텍스처: Poly Haven · ambientCG (CC0)"
    ),
}

SITES = {s["code"]: s for s in (GBG, DSG, HSF, KRM, KGI)}


# ------------------------------------------------------------------ 무결성

def _check():
    """컬렉션 이름과 그룹 코드가 사이트끼리 겹치지 않는지 확인한다.

    겹치면 조용한 오분류가 나므로 import 시점에 터뜨린다.
    """
    seen_coll, seen_group = {}, {}
    for code, s in SITES.items():
        for coll, grp in s["collections"].items():
            if coll in seen_coll:
                raise ValueError(
                    "컬렉션 이름 중복: %r 가 %s 와 %s 에 모두 있다"
                    % (coll, seen_coll[coll], code))
            seen_coll[coll] = code
            if grp in seen_group:
                raise ValueError(
                    "그룹 코드 중복: %r 가 %s 와 %s 에 모두 있다"
                    % (grp, seen_group[grp], code))
            seen_group[grp] = code
        for _, rules, fallback in s["name_rules"]:
            for _, grp in list(rules) + [(None, fallback)]:
                if grp in seen_group and seen_group[grp] != code:
                    raise ValueError(
                        "그룹 코드 중복: %r 가 %s 와 %s 에 모두 있다"
                        % (grp, seen_group[grp], code))
                seen_group[grp] = code
    # 비상업 라이선스 에셋이 익스포트 대상에 섞이면 조용히 라이선스를 위반한다.
    # 등록을 깜빡 되돌리는 사고를 import 시점에 터뜨린다.
    for coll in NC_COLLECTIONS:
        if coll in seen_coll:
            raise ValueError(
                "NC 라이선스 컬렉션 %r 가 %s 에 등록돼 있다 — 오버데어로 나간다. "
                "렌더 전용이므로 collections 에서 빼야 한다" % (coll, seen_coll[coll]))


_check()


def site_of_collection(coll_name):
    """컬렉션 이름 → 사이트 코드. 없으면 None."""
    for code, s in SITES.items():
        if coll_name in s["collections"]:
            return code
        for parent, _, _ in s["name_rules"]:
            if coll_name == parent:
                return code
    return None


def group_of(coll_name, obj_name):
    """컬렉션 + 객체 이름 → 익스포트 그룹 코드.

    export_overdare.group_of 가 이 함수를 쓰도록 바꾸면 궁궐이 늘어나도
    if 사슬을 건드릴 필요가 없다. 경복궁에 대해서는 기존 결과와 완전히 같다.
    """
    for s in SITES.values():
        grp = s["collections"].get(coll_name)
        if grp:
            return grp
        for parent, rules, fallback in s["name_rules"]:
            if coll_name != parent:
                continue
            for prefix, g in rules:
                if obj_name.startswith(prefix):
                    return g
            return fallback
    return "MISC"


DSG_COLLECTIONS = tuple(DSG["collections"].keys())
