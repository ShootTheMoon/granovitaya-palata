# -*- coding: utf-8 -*-
"""모스크바 크렘린 실측 치수표.

형식과 규약은 deoksugung/measured.py · hwaseong/uigwe.py 와 같다.

    key: (값, 출처, 신뢰도)

    신뢰도  'measured' 도면·표·실측 폴리곤에서 직접 읽음
            'counted'  개수를 세어 유도
            'derived'  비례·계산에서 유도. 실측으로 대체되어야 함

**measured 와 derived 가 섞여 구분이 안 되는 상태**가 피해야 할 실패다.

────────────────────────────────────────────────────────────────────────
자료 사정 — 이 파일이 왜 이렇게 생겼는가

크렘린은 러시아 대통령 관저이자 보안 시설이라 **공개된 현대 CAD·실측 도면이
사실상 없다.** kreml.ru 도 서술형 설명과 사진만 낸다. 그래서 치수 출처가
셋으로 갈린다.

  1) **높이** — ru.wikipedia 「Башни Московского Кремля」 종합표. 20기 전부 있다.
  2) **평면 치수와 위치** — 어느 문헌에도 없다. **OSM 폴리곤에서 직접 쟀다.**
     크렘린 탑은 way 가 아니라 멀티폴리곤 릴레이션이라 `nwr` 로 뽑아야 나온다
     (`way["building"]` 으로는 매표소·마구간만 26개 나오고 탑은 0개다).
  3) **결측** — 블라고베셴스키 대성당·테렘궁·아르세날 파사드 치수 등은 아직
     못 구했다. 바르테네프 『Московский Кремль в старину и теперь』(1912–16,
     퍼블릭 도메인, https://electro.nekrasovka.ru/books/705)가 유일하게 실측
     도면을 담은 문헌이다. derived 로 남겨 두고 거기서 채운다.
────────────────────────────────────────────────────────────────────────
"""

import math

# ---------------------------------------------------------------- 단위
#
# 러시아 역사 단위. uigwe.ja() 와 대칭이 되게 둔다.
#   1 сажень(사젠) = 3 аршин(아르신) = 7 фут = 2.1336 m
#   1 аршин = 0.7112 m
SAZHEN_M = (2.1336, '1835년 제정 러시아 도량형법. 7 영국피트로 고정', 'measured')
ARSHIN_M = (0.7112, 'SAZHEN_M / 3', 'derived')


def sazhen(s, arshin=0.0):
    """사젠·아르신 → 미터."""
    return s * SAZHEN_M[0] + arshin * ARSHIN_M[0]


# ---------------------------------------------------------------- 성벽

WALL = {
    # 전 출처(ru/en 위키)가 일치하는 공표값.
    'perimeter_official': (2235.0, 'ru/en wiki 「Кремлёвская стена」 전 출처 일치',
                           'measured'),
    # OSM castle relation 1360641 폴리곤을 직접 재서 얻은 값. 공표값보다 긴 것은
    # 폴리곤이 탑 20기의 돌출부를 전부 돌기 때문이다 (아래 length_effective 참조).
    'perimeter_osm': (2570.6, 'OSM relation 1360641 폴리곤 실측 (1204 pt)', 'measured'),
    # 위 둘레에서 탑이 성벽에 물린 전면(273.9 m)을 뺀 값.
    # **공표 2,235 m 와 2.8% 차이다.** 두 숫자가 이렇게 맞는다는 것은
    # 공표값이 '탑을 제외한 순수 성벽 길이'라는 뜻이고, 여장 개수를 이 길이에
    # 걸어야 한다는 근거가 된다.
    'length_effective': (2296.7, 'perimeter_osm(2570.6) − 탑 전면 합(273.9)', 'derived'),
    'area_osm': (265057.0, 'OSM relation 1360641 폴리곤 실측', 'measured'),
    'area_official': (277000.0, 'ru.wiki 27.7 ha', 'measured'),
    # ⚠ 공표 둘레 2,235 m 와 공표 면적 27.7 ha 는 **삼각형으로는 양립 불가능**하다.
    #   둘레 2,235 m 삼각형의 최대 면적은 정삼각형일 때 (√3/4)·745² = 240,300 m²
    #   로 27.7 ha 에 못 미친다. '불규칙 삼각형'은 서술이지 기하가 아니다.
    #   → 평면은 반드시 OSM 폴리곤을 쓴다. 640/832/747 삼각형은 검산용이다.
    'side_south': (sazhen(300), 'ru.ruwiki 300 саж (모스크바 강변)', 'derived'),
    'side_west': (sazhen(390), 'ru.ruwiki 390 саж (네글린나야·알렉산드로프 정원)',
                  'derived'),
    'side_east': (sazhen(350), 'ru.ruwiki 350 саж (붉은광장)', 'derived'),

    'height_min': (5.0, 'ru/en wiki. 모스크바 강변 구간', 'measured'),
    'height_max': (19.0, 'ru/en wiki. 붉은광장 구간', 'measured'),
    'thick_min': (3.5, 'ru/en wiki 전 출처 일치', 'measured'),
    # ⚠ 상충: ru.wiki 「Кремлёвская стена」는 5.5, 「Московский Кремль」와 en.wiki 는 6.5.
    'thick_max': (6.5, 'ru.wiki 「Московский Кремль」·en.wiki (다수설). '
                       '「Кремлёвская стена」는 5.5 로 상충', 'measured'),
    'walkway_min': (2.0, 'en.wiki 전투 통로(боевой ход)', 'measured'),
    'walkway_max': (4.5, 'en.wiki', 'measured'),
    # 외부 벽돌 껍질 두께. 안쪽은 백석 잡석 + 모르타르 충전이다.
    'shell_thick': (1.125, 'ru.wiki 110~115 cm 의 중앙값', 'measured'),
    'brick_l': (0.30, 'ru.wiki 30×14×17 cm (31×15×9 cm 병기)', 'measured'),
    'brick_w': (0.14, 'ru.wiki', 'measured'),
    'brick_h': (0.17, 'ru.wiki', 'measured'),
    'built_from': (1485, 'ru/en wiki', 'measured'),
    'built_to': (1495, 'ru/en wiki. 해자 포함 전체는 1516', 'measured'),
}

# ---------------------------------------------------------------- 여장
#
# 제비꼬리형(зубцы «ласточкин хвост»). 이탈리아 기벨린식 메를론이다 —
# 밀라노 스포르차 성(15c)·베로나 카스텔베키오(14c)가 직접 모델이고,
# 성벽을 지은 것이 이탈리아 건축가들(Солари·Фрязин)이라 그대로 건너왔다.
MERLON = {
    # ⚠ 상충: ru.wiki 「Кремлёвская стена」 본문은 1,044. 1,045 가 압도적 다수설이다.
    'count': (1045, 'en.wiki 인포박스·ru.wiki 「Московский Кремль」·러시아 매체 다수. '
                    '「Кремлёвская стена」 본문은 1044 로 상충', 'counted'),
    'height_min': (2.0, 'ru/en wiki', 'measured'),
    'height_max': (2.5, 'ru/en wiki', 'measured'),
    'width_max': (2.0, 'ru.wiki «до двух метров»', 'measured'),
    'thick_min': (0.65, 'ru/en wiki 일치', 'measured'),
    # ⚠ ru.wiki 0.72 / en.wiki 0.75. 실질 차이는 무시할 수준이다.
    'thick_max': (0.75, 'en.wiki (ru.wiki 는 0.72)', 'measured'),
    # 피치 = 성벽 실길이 / 개수. 공표 둘레로 나누면 2.139 가 나오는데, 그 둘레는
    # 탑을 제외한 값이므로 실제로 여장을 놓을 길이는 length_effective 다.
    'pitch': (2296.7 / 1045.0, 'WALL.length_effective / MERLON.count = 2.198 m',
              'derived'),
    # 폭 + 틈 = 피치. **크렘린은 여장이 넓고 틈이 좁다** — 사진에서 총안 사이가
    # 슬릿에 가깝다. width_max 2.0 을 그대로 쓰면 틈이 0.2 m 라 지나치므로
    # 1.75 로 두고 틈 0.45 를 남긴다. 처음에 1.62/0.58 로 잡았더니 틈이 너무
    # 벌어져 서양 성곽의 일반 크레넬처럼 보였다.
    'width': (1.75, 'pitch 2.198 에서 틈 0.45 를 뺀 값. width_max 2.0 이내',
              'derived'),
    'gap': (0.45, '위와 같음', 'derived'),
    # 뿔 사이 V 홈. 제비꼬리를 만드는 유일한 파라미터라 실루엣에 직접 걸린다.
    'notch_depth': (0.72, '사진 비례 추정. Commons Category:Moscow Kremlin Wall '
                          '253파일로 검증할 것', 'derived'),
    'notch_width': (0.58, '위와 같음', 'derived'),
    # 미석(여장 아래 연속 띠)
    'sill_thick': (0.16, 'hwaseong/fortress.MISEOK_T 를 따름', 'derived'),
}

# ---------------------------------------------------------------- 탑 20기
#
# 열의 출처·신뢰도는 열마다 같으므로 여기 한 번만 적는다.
# (20기 × 8열 = 160개 3-튜플을 쓰는 것보다 낡을 위험이 적다.)
TOWER_COLUMNS = {
    'year':    ('ru.wikipedia 「Башни Московского Кремля」', 'measured'),
    'height':  ('ru.wikipedia 「Башни Московского Кремля」 표 (직접 확인)', 'measured'),
    'osm_h':   ('OSM relation height 태그', 'measured'),
    'x':       ('OSM 폴리곤 무게중심. 앵커 55.7516212N/37.6181220E 기준 동쪽 m',
                'measured'),
    'y':       ('OSM 폴리곤 무게중심. 앵커 기준 북쪽 m', 'measured'),
    'w':       ('OSM 폴리곤 최소외접사각형의 긴 변', 'measured'),
    'd':       ('OSM 폴리곤 최소외접사각형의 짧은 변', 'measured'),
    'yaw':     ('OSM 폴리곤 주축 각(도). +X(동)에서 반시계', 'measured'),
    'circ':    ('4πA/P². 1.0=원, 0.785=정사각형', 'measured'),
    'shape':   ('circ 로 판정. >0.93 원형, >0.83 팔각, 나머지 사각', 'derived'),
    'star':    ('en.wiki 「Kremlin stars」. 1937년 설치 5기', 'measured'),
}

# ⚠ **높이 기준면이 탑마다 다르다.**
#   Троицкая 80 m 는 알렉산드로프 정원(저지대) 쪽에서 잰 값이다. 크렘린 안쪽
#   지면 기준으로는 훨씬 낮다. datum 열이 그것을 표시한다.
#     'kremlin'  크렘린 내부 지면 기준
#     'outside'  성 바깥 저지대 기준 (그만큼 지반을 낮춰야 실루엣이 맞는다)
#
# ⚠ **상충 2건.** Оружейная 와 Средняя Арсенальная 는 ru.wiki 가 둘 다 38.9 로
#   같은 값을 적었는데 OSM 은 32.65 / 28.9 로 크게 다르다. 같은 값 두 개가
#   나란히 있는 것 자체가 전사 오류로 보인다. 바르테네프 도면으로 확정할 것.
#   그때까지 height 는 'derived' 취급한다 (TOWER_CONFLICT 참조).
TOWER_CONFLICT = {'Оружейная', 'Средняя Арсенальная', 'Благовещенская', 'Царская'}

# 이름, 연도, 공표높이, OSM높이, x, y, 폭, 깊이, yaw, 원형도, 형태, 별, datum
TOWERS = {
    'Троицкая': dict(
        rel='1360627', year=1495, height=80.0, osm_h=80.0,
        x=-224.74, y=72.92, w=20.20, d=30.59, yaw=74.0, circ=0.59,
        shape='square', star=True, datum='outside'),
    'Спасская': dict(
        rel='1360656', year=1491, height=71.0, osm_h=71.0,
        x=204.77, y=100.55, w=25.59, d=18.03, yaw=47.0, circ=0.52,
        shape='square', star=True, datum='kremlin'),
    'Никольская': dict(
        rel='1359372', year=1491, height=70.4, osm_h=70.4,
        x=-19.56, y=319.80, w=27.31, d=15.12, yaw=45.0, circ=0.63,
        shape='square', star=True, datum='kremlin'),
    'Водовзводная': dict(
        rel='1360648', year=1488, height=61.25, osm_h=61.25,
        x=-282.98, y=-391.27, w=12.55, d=12.63, yaw=82.0, circ=1.00,
        shape='round', star=True, datum='outside'),
    'Угловая Арсенальная': dict(
        rel='1360653', year=1492, height=60.2, osm_h=60.0,
        x=-99.90, y=388.98, w=17.03, d=16.80, yaw=50.0, circ=0.99,
        shape='round', star=False, datum='outside'),
    'Боровицкая': dict(
        rel='1360630', year=1490, height=54.0, osm_h=54.0,
        x=-351.15, y=-301.02, w=13.65, d=19.36, yaw=31.0, circ=0.72,
        shape='square', star=True, datum='outside'),
    'Беклемишевская': dict(
        rel='1360651', year=1488, height=46.2, osm_h=46.2,
        x=318.31, y=-209.51, w=10.08, d=10.04, yaw=29.0, circ=1.00,
        shape='round', star=False, datum='outside'),
    'Комендантская': dict(
        rel='1360655', year=1495, height=41.25, osm_h=41.25,
        x=-284.23, y=-111.42, w=10.08, d=8.91, yaw=68.0, circ=0.78,
        shape='square', star=False, datum='kremlin'),
    'Оружейная': dict(
        rel='1360631', year=1493, height=38.9, osm_h=32.65,
        x=-338.84, y=-246.98, w=10.29, d=10.14, yaw=75.0, circ=0.79,
        shape='square', star=False, datum='kremlin'),
    'Средняя Арсенальная': dict(
        rel='1360654', year=1493, height=38.9, osm_h=28.9,
        x=-159.00, y=232.01, w=16.11, d=9.64, yaw=70.0, circ=0.58,
        shape='square', star=False, datum='kremlin'),
    'Тайницкая': dict(
        rel='3229147', year=1485, height=38.4, osm_h=38.4,
        x=-16.53, y=-252.62, w=20.37, d=16.51, yaw=16.0, circ=0.78,
        shape='square', star=False, datum='outside'),
    'Набатная': dict(
        rel='1360661', year=1495, height=38.0, osm_h=38.0,
        x=233.52, y=21.29, w=9.85, d=9.84, yaw=18.0, circ=0.79,
        shape='square', star=False, datum='kremlin'),
    'Константино-Еленинская': dict(
        rel='1360645', year=1490, height=36.8, osm_h=36.8,
        x=263.64, y=-50.27, w=15.48, d=16.03, yaw=24.0, circ=0.79,
        shape='square', star=False, datum='kremlin'),
    'Первая безымянная': dict(
        rel='1360642', year=1485, height=34.15, osm_h=34.15,
        x=50.81, y=-235.10, w=11.46, d=12.32, yaw=15.0, circ=0.78,
        shape='square', star=False, datum='outside'),
    'Сенатская': dict(
        rel='1359374', year=1491, height=34.3, osm_h=34.0,
        x=90.42, y=207.93, w=8.47, d=9.77, yaw=47.0, circ=0.78,
        shape='square', star=False, datum='kremlin'),
    'Благовещенская': dict(
        rel='3229300', year=1488, height=32.45, osm_h=30.7,
        x=-183.95, y=-324.18, w=11.28, d=9.67, yaw=32.0, circ=0.78,
        shape='square', star=False, datum='outside'),
    'Вторая безымянная': dict(
        rel='3229567', year=1485, height=30.2, osm_h=30.2,
        x=137.90, y=-222.94, w=10.16, d=9.09, yaw=8.0, circ=0.78,
        shape='square', star=False, datum='outside'),
    'Петровская': dict(
        rel='1360660', year=1485, height=27.15, osm_h=27.15,
        x=243.13, y=-213.04, w=9.62, d=11.81, yaw=1.0, circ=0.78,
        shape='square', star=False, datum='outside'),
    'Царская': dict(
        rel='1360663', year=1680, height=16.7, osm_h=16.0,
        x=214.75, y=68.38, w=4.06, d=4.79, yaw=20.0, circ=0.78,
        shape='square', star=False, datum='wall'),
    # 유일한 외곽 방어탑(отводная стрельница). 성벽에 붙어 있지 않고
    # 트로이츠키 다리 건너편에 홀로 서 있다.
    'Кутафья': dict(
        rel='3061015', year=1516, height=13.5, osm_h=13.5,
        x=-334.81, y=100.63, w=15.56, d=22.85, yaw=75.0, circ=0.76,
        shape='square', star=False, datum='outside'),
}

# ---------------------------------------------------------------- 루비 별
#
# 1935.10.25 준보석 별 4기(낫과망치 문양) → 1937.11.02 혁명 20주년에 루비
# 유리로 교체하며 Водовзводная 가 추가돼 5기가 됐다. 그 이전에는 제정기
# 쌍두독수리 청동상이었다.
STARS = {
    'Водовзводная': (3.0, 'en.wiki 「Kremlin stars」 날개 끝점 간 거리', 'measured'),
    'Боровицкая': (3.2, 'en.wiki', 'measured'),
    'Троицкая': (3.5, 'en.wiki', 'measured'),
    'Никольская': (3.75, 'en.wiki', 'measured'),
    'Спасская': (3.75, 'en.wiki', 'measured'),
}
STAR_SPEC = {
    'mass_kg': (1000.0, 'en.wiki 개당 약 1 t', 'measured'),
    'glass_thick': (0.007, 'en.wiki 6~8 mm 의 중앙값', 'measured'),
    'glass_area': (6.0, 'en.wiki 별당 약 6 m²', 'measured'),
    'gilding_um': (40.0, 'en.wiki 금도금 40 μm, 5기 합계 금 11 kg', 'measured'),
    'lamp_w': (4350.0, 'en.wiki 3.7~5 kW 의 중앙값', 'measured'),
    'installed': (1937, 'en.wiki 루비 유리 별 교체', 'measured'),
}

# ---------------------------------------------------------------- 성당·궁전
#
# ❌ 로 시작하는 주석은 아직 못 구한 값이다. 바르테네프에서 채운다.

# ★ **OSM 폴리곤 실측이 공표치를 재현했다.**
#   우스펜스키 공표 43 × 29 m ↔ OSM 실측 43.10 × 28.62 m (오차 0.2% / 1.3%).
#   탑 20기의 평면 치수를 OSM 에서 잰 것이 옳았다는 독립 확증이다.
#   그래서 아래 성당들의 결측 치수도 같은 방법으로 채웠다.
#
#   공통 열: x, y = 앵커 기준 (동 m, 북 m) / w, d = 최소외접사각형 / yaw = 주축 각
SQUARE_AREA = (9820.0, 'OSM relation 1359293 「Соборная площадь」 폴리곤 실측',
               'measured')

USPENSKY = {   # Успенский собор — 성모승천 대성당, 1475–79, Fioravanti
    'rel': ('3028585', 'OSM', 'measured'),
    'x': (-66.58, 'OSM 폴리곤 무게중심', 'measured'),
    'y': (-76.79, 'OSM 폴리곤 무게중심', 'measured'),
    'yaw': (16.0, 'OSM 폴리곤 주축', 'measured'),
    'length': (43.10, 'OSM 폴리곤 실측. 공표 43 m 와 0.2% 차', 'measured'),
    'width': (28.62, 'OSM 폴리곤 실측. 공표 29 m 와 1.3% 차', 'measured'),
    'height_cross': (49.0, 'ru.wiki. 중앙 돔 십자가 상단까지', 'measured'),
    'height_wall': (21.0, 'ru.wiki. 벽체 + 자코마라 상단', 'measured'),
    'iconostasis_h': (16.0, 'ru.wiki', 'measured'),
    'domes': (5, '6기둥·5앱스·5돔. 돔은 동쪽으로 치우쳐 배치', 'counted'),
    'bays': (12, '내부를 동일 크기 정사각형 12개로 분할', 'counted'),
    'piers_round': (4, '동측 2개는 각형 피어, 나머지 4개는 원형', 'counted'),
    'built': (1479, 'ru/en wiki', 'measured'),
}

ARKHANGELSKY = {   # Архангельский собор — 대천사 대성당, 1505–08, Алевиз Новый
    'height_wall': (21.0, 'ru.wiki', 'measured'),
    'iconostasis_h': (13.0, 'ru.wiki', 'measured'),
    'domes': (5, '6기둥·5앱스·5돔', 'counted'),
    # 파사드가 베네치아 르네상스다 — 필라스터 + 아칸서스 주두, 그리고
    # **자코마라를 백석 가리비 껍데기(раковина)로 채운 것**이 가장 상징적이다.
    'shell_zakomara': (True, 'ru.wiki', 'measured'),
    'built': (1508, 'ru/en wiki', 'measured'),
    # 문헌에 없던 평면 치수를 OSM 폴리곤에서 실측했다 (derived → measured).
    'rel': ('1359243', 'OSM', 'measured'),
    'x': (-20.42, 'OSM 폴리곤 무게중심', 'measured'),
    'y': (-160.23, 'OSM 폴리곤 무게중심', 'measured'),
    'yaw': (7.0, 'OSM 폴리곤 주축', 'measured'),
    'length': (34.71, 'OSM 폴리곤 실측', 'measured'),
    'width': (30.00, 'OSM 폴리곤 실측', 'measured'),
    # 처음에 40 m 로 추정했더니 cathedral.build_church 의 드럼 높이 역산이
    # **-4.4 m** 로 나왔다 — 벽체 21 m 에 폭 30 m 짜리 5돔을 얹으면 40 m 에
    # 들어갈 수가 없다. 기하가 추정치를 반증한 셈이다. 우스펜스키(벽체 21,
    # 총고 49)와 같은 벽체 높이이므로 총고도 그에 준하는 값이어야 한다.
    'height_cross': (47.5, '벽체 21 m(measured) + 돔 기하 정합에서 역산. '
                           '우스펜스키 49 m 와의 비례로 교차 확인', 'derived'),
}

BLAGOVESHCHENSKY = {   # Благовещенский собор — 수태고지 대성당, 1484–89
    'domes': (9, 'ru.wiki. 중앙 대돔 1 + 소돔 8 (천사 9계급)', 'counted'),
    'built': (1489, 'ru.wiki', 'measured'),
    'gilded_1508': (True, 'ru.wiki. 별칭 «златоверхая»(금빛 지붕)', 'measured'),
    # 평면은 OSM 실측으로 확정했다. **주축이 우스펜스키와 반대다** —
    # 폭(26.59)이 길이(23.21)보다 커서 남북으로 긴 평면이다. 3면 갤러리가
    # 붙어 있어 그렇다.
    'rel': ('1359251', 'OSM', 'measured'),
    'x': (-77.74, 'OSM 폴리곤 무게중심', 'measured'),
    'y': (-179.25, 'OSM 폴리곤 무게중심', 'measured'),
    'yaw': (14.0, 'OSM 폴리곤 주축', 'measured'),
    'length': (23.21, 'OSM 폴리곤 실측 (갤러리 포함)', 'measured'),
    'width': (26.59, 'OSM 폴리곤 실측 (갤러리 포함)', 'measured'),
    # ❌ 높이는 여전히 미확보. 처음에 32/14 로 잡았더니 아르한겔스키와 같은
    #    이유로 드럼 높이가 클램프됐다. 9돔이라 중앙 돔이 작아지는 것을
    #    반영하고(cathedral.build_church 의 r_c 보정) 정합하는 값으로 올렸다.
    'height_cross': (37.0, '우스펜스키 49 m × 0.75 + 돔 기하 정합에서 역산',
                     'derived'),
    'height_wall': (16.0, '위와 같음', 'derived'),
}

IVAN_BELL = {   # Колокольня Ивана Великого — 이반 대제 종탑
    'height': (81.0, 'ru.wiki. 십자가 포함 총고', 'measured'),
    'height_1508': (60.0, 'ru.wiki. 1600년 증축 전 원래 높이', 'measured'),
    'tiers': (3, 'ru.wiki. 팔각형 3단(три восьмерика) + 원통 드럼', 'counted'),
    'wall_t_1f': (5.0, 'ru.wiki. 1층 벽 두께 최대', 'measured'),
    'wall_t_2f': (2.5, 'ru.wiki', 'measured'),
    'wall_t_top': (0.8, 'ru.wiki 「벽돌 3장 두께」', 'derived'),
    'inner_dia': (5.0, 'ru.wiki. 하부 내부 직경', 'measured'),
    'base_dia': (25.0, 'ru.wiki. 기초 면 직경', 'measured'),
    'found_depth': (5.35, 'ru.wiki 5.2~5.5 m 의 중앙값', 'measured'),
    'bells': (34, 'ru.wiki', 'counted'),
    'built': (1508, 'Бон Фрязин. 1600 Фёдор Конь 증축', 'measured'),
    # OSM 실측. 원형도 0.81 이 **팔각형**을 가리킨다(정사각 0.785, 원 1.0) —
    # «три восьмерика» 라는 문헌 서술과 지오메트리가 일치한다.
    'rel': ('1359281', 'OSM. 태그 이름은 Церковь Иоанна Лествичника', 'measured'),
    'x': (5.65, 'OSM 폴리곤 무게중심', 'measured'),
    'y': (-100.19, 'OSM 폴리곤 무게중심', 'measured'),
    'yaw': (19.0, 'OSM 폴리곤 주축', 'measured'),
    'width': (14.88, 'OSM 폴리곤 실측. 문헌의 기초 면 직경 25 m 는 지하 기초다',
              'measured'),
    'depth': (14.63, 'OSM 폴리곤 실측', 'measured'),
}

# 성당광장 나머지 — 전부 OSM 폴리곤 실측
SQUARE_BUILDINGS = {
    # 이름: (rel, x, y, w, d, yaw, 높이, 높이신뢰도)
    '우스펜스카야 종루': ('1359278', -5.61, -82.11, 28.44, 44.80, 18.0, 33.5, 'derived'),
    '총주교궁': ('1359248', -88.90, -46.38, 83.12, 55.78, 10.0, 22.0, 'derived'),
    '12사도 교회': ('1359249', -43.52, -27.80, 19.00, 18.22, 23.0, 30.0, 'derived'),
    '포테시니 궁': ('1359337', -232.31, -42.01, 28.37, 28.39, 73.0, 24.0, 'derived'),
}

# 궁전·관청 — 평면은 OSM 실측, 높이는 문헌 또는 유도
# ⚠ 대크렘린궁 OSM 폴리곤(176 × 145 m)은 **복합체 전체**다. 테렘궁·파세트궁·
#   조로타야 차리치나 팔라타가 한 폴리곤에 묶여 있어서, 공표 파사드 125 m 와
#   직접 비교하면 안 된다. 파사드는 남면(모스크바 강 쪽) 한 변이다.
COMPLEX = {
    '대크렘린궁': ('225033', -150.82, -153.96, 176.44, 145.23, 14.0, 47.0, 'measured'),
    '상원궁': ('1359233', 27.04, 178.20, 137.41, 138.72, 47.0, 27.0, 'derived'),
    '무기고': ('51497', -115.95, 222.90, 306.93, 87.24, 69.0, 24.0, 'measured'),
    '오루제이나야 팔라타': ('1359335', -293.65, -225.33, 90.88, 34.91, 54.0, 22.0, 'derived'),
    '국립크렘린궁': ('3031379', -163.48, -21.87, 130.74, 72.66, 77.0, 29.0, 'derived'),
}

GRANOVITAYA = {   # Грановитая палата — 파세트 궁, 1487–91
    'hall_area': (495.0, 'ru.wiki. 정사각형 옥좌홀', 'measured'),
    'hall_side': (math.sqrt(495.0), 'sqrt(495) = 22.25 m', 'derived'),
    'vault_h': (9.0, 'ru.wiki. 볼트 최고점', 'measured'),
    'floors': (2, '상층 옥좌홀 + 하층 подклет', 'counted'),
    'built': (1491, 'Марко Руффо + П.А. Солари', 'measured'),
    # 동측 파사드의 면치기 러스티케이션(гранёный руст)이 이름의 유래다.
    'rustication': (True, 'ru.wiki. 백석 다이아몬드 커트 블록', 'measured'),

    # ---------------------------------------------------------- 내부
    #
    # 2026-08-23 Табл.12 실측. 도판 tab12_p047.jpg 를 픽셀로 재서 얻었다.
    #
    # 축척 확정 — 이 도판은 **입면과 평면의 축척이 다르다**. 축척자 두 개 중
    #   м. фасада 만 눈금이 고르게 읽혔다(11눈금 0~10 m → 38.25 px/m).
    #   м. планов 는 눈금 간격이 96/91/83.5 px 로 비선형이라 못 쓴다.
    #   그런데 **단면은 입면 축척으로 그려져 있다**: 바닥→천장 344 px 를
    #   38.25 로 나누면 8.99 m 로, 문헌 vault_h 9.0 을 0.1% 오차로 재현한다.
    #   평면은 홀 내부를 단면의 22.43 m 에 맞춰 역산해 18.50 px/m 로 잡았다.
    #
    # 교차검증 — 두 도면이 서로를 확인해 준다:
    #   홀 내부  단면 22.43 / 평면 22.54 × 22.27 / sqrt(495) = 22.25
    #   중앙 기둥 평면 2.27 × 2.22 / 단면 2.48
    #   기둥 중심이 홀 중심에서 **0.09 m** — 정중앙이 맞다
    'hall_inner': (22.4, 'Табл.12 단면 858 px / 38.25 + 평면 대조. '
                         'sqrt(hall_area) 22.25 와 0.7% 차', 'measured'),
    'pier_side': (2.3, 'Табл.12 평면 42×41 px / 18.50, 단면 95 px / 38.25 로 대조',
                  'measured'),
    # 아치는 반원이다. 베이 반경 = 홀 내부 / 4 = 5.6 m 이고
    # 스프링잉 = 볼트 최고점 - 반경 = 9.0 - 5.6 = 3.4 로 떨어진다.
    # 단면에서 기둥 주두를 직접 재면 3.2~3.6 m 라 이 값과 맞는다.
    # ⚠ 폭이 있는 이유: 단면의 바닥선이 어느 가로선인지 스캔 해상도에서
    #   확정이 안 된다(y≈385 의 이중선 vs y≈430 의 해칭 상단). 문헌 9.0 을
    #   기준으로 두고 스프링잉을 기하에서 역산했다.
    'vault_spring_h': (3.4, 'vault_h 9.0 - 베이 반경 5.6. Табл.12 단면 실측 3.2~3.6 과 일치',
                       'derived'),
    'vault_bays': (4, '중앙 기둥 1개에서 네 모서리로 뻗는 대각 능선. Табл.12 평면의 점선',
                   'counted'),

    # 벽 두께 — Табл.12 평면 실측 (18.50 px/m)
    'wall_east': (2.0, 'Табл.12 평면 37 px', 'measured'),
    'wall_north': (1.7, 'Табл.12 평면 31 px', 'measured'),
    'wall_south': (2.3, 'Табл.12 평면 43 px', 'measured'),
    'wall_seni': (2.5, 'Табл.12 평면 46 px. 홀과 сени 를 가르는 벽', 'measured'),
    'seni_depth': (5.1, 'Табл.12 평면 94 px. сени(현관홀) 안목', 'measured'),
    'seni_outer': (1.2, 'Табл.12 평면 23 px. сени 외벽', 'measured'),
    # ⚠ 위 값을 다 더하면 장변 33.4 m 인데 README §06 의 「주 블록 34.9」와
    #   4% 다르다. README 쪽은 OSM 폴리곤 분해라 derived 이고, 이쪽은 도판
    #   실측이다. 도판을 따른다.
    'block_long': (33.4, 'Табл.12 평면 617 px. README 의 derived 34.9 와 4% 차',
                   'measured'),
    'block_short': (26.3, 'Табл.12 평면 486 px. README 의 derived 27.27 과 4% 차',
                    'measured'),

    # ---------------------------------------------------------- 수직 레벨
    #
    # Табл.12 「Главный фасад」 실측. 지면선 y=915 를 0 으로 두고 위로 재서
    # 입면 축척 38.25 px/m 로 나눴다.
    #
    # ★ 기하가 닫힌다 — 홀 바닥을 подклет 상단(3.0)으로 두면 큰 창이
    #   바닥 위 4.1~8.1 m 에 오고, 볼트 루넷은 스프링잉 3.4 에서 마루 9.0
    #   까지다. **창이 루넷 안에 정확히 들어간다.** 이 건물의 창이 높이
    #   달린 이유가 여기서 설명된다.
    'podklet_h': (3.0, 'Табл.12 입면 y800→915, 115 px. 러스티케이션이 시작되는 높이',
                  'measured'),
    'window_sill': (4.1, 'Табл.12 입면 y645 = 지면 위 7.06 m, 홀 바닥 3.0 을 뺀 값',
                    'derived'),
    'window_head': (8.1, 'Табл.12 입면 y490 = 지면 위 11.11 m, 홀 바닥 3.0 을 뺀 값',
                    'derived'),
    'wall_top': (15.7, 'Табл.12 입면 y314. 러스티케이션 벽 상단', 'measured'),
    'cornice_top': (18.1, 'Табл.12 입면 y221', 'measured'),
    'roof_apex': (23.5, 'Табл.12 입면 y16. ⚠ OSM height 태그 21 m 와 12% 차 — '
                        '태그가 처마까지일 가능성이 있다', 'measured'),
    # 위쪽 작은 창 2개는 볼트 마루(바닥+9.0 = 지면 위 12.0)보다 높아서
    # 홀이 아니라 지붕 밑 공간으로 열린다. 실내에는 넣지 않는다.
    'window_upper_note': (0.0, 'Табл.12 입면 y365~450 의 작은 창은 볼트 위라 '
                               '홀에 빛을 주지 않는다', 'counted'),

    # ---------------------------------------------------------- 실내 요소
    #
    # 2026-08-23 Табл.13·14·15 를 PDF(p049·p051·p053)에서 렌더해 확보한 뒤
    # 추가. 그 전까지는 이 도판들이 없어서 실내가 빈 방이었다.
    #
    # 다도 — 단면에서 **전폭을 가로지르는 y≈385 의 이중선**이 이것이다.
    # 처음엔 그걸 바닥선으로 읽었는데 그러면 볼트가 7.58 m 로 문헌 9.0 과
    # 안 맞았다. 바닥은 그보다 아래(해칭 상단 y≈430)이고 그 사이 45 px 가
    # 다도다. Табл.14 대홀 사진에도 벽 밑을 도는 밝은 띠로 나온다.
    'dado_h': (1.2, 'Табл.12 단면 y385~430, 45 px / 38.25. '
                    'Табл.14 사진과 일치', 'measured'),
    # 창은 **반원 아치머리에 안쪽으로 넓어지는 사면 여벽**이다.
    # Табл.14 에서 명확하다 — 입면(Табл.12)의 사각 나리치닉은 바깥 틀이고
    # 안쪽 개구부는 아치다. 벽이 2 m 두꺼워 이 사면의 그림자가 크다.
    'window_arched': (1.0, 'Табл.14 대홀 내부 사진. 반원 아치머리', 'measured'),
    'window_splay': (0.55, 'Табл.14. 안쪽으로 넓어지는 폭. 벽 두께 2.0 대비',
                     'derived'),

    # ---------------------------------------------------------- 포털
    #
    # 2026-08-23. ⚠ **Табл.15(포털 전용 도판)에는 축척자가 없다.** 정투영
    #   실측도가 아니라 사진이다. Табл.13(сени 내부)도 마찬가지다. 그래서 이
    #   네 값은 measured 가 아니라 **derived** 다.
    #
    # 앵커: 문 손잡이 높이 1.0 m. Табл.15 에서 바닥선 y≈1545 px, 손잡이
    #   y≈1310 px (1498 px 폭 기준) → 235 px/m. 손잡이가 0.9~1.1 m 사이라고
    #   보면 축척이 214~261 px/m 이므로 **아래 값은 ±10% 대역**이다.
    #
    # 교차확인 하나가 붙는다 — 이 축척으로 포털 전고가 5.5 m 인데
    #   сени 원통볼트 마루가 바닥 위 5.21 m 다. 포털 꼭대기가 сени 천장에
    #   거의 닿는다. 우연이라기엔 잘 맞고, 손잡이를 0.95 m 로 보면 5.2 로
    #   정확히 닿는다. 축척이 이 근처인 것은 맞다고 본다.
    'portal_open_w': (1.45, 'Табл.15 개구부 345 px / 235 px/m. 쌍여닫이',
                      'derived'),
    'portal_open_h': (2.75, 'Табл.15 개구부 650 px / 235 px/m', 'derived'),
    'portal_frame_w': (3.30, 'Табл.15 플린트 바깥 780 px / 235 px/m', 'derived'),
    'portal_frame_h': (5.50, 'Табл.15 바닥~오지형 첨두 1305 px / 235 px/m. '
                             'сени 볼트 마루 5.21 과 거의 일치', 'derived'),
    # ★ 위치는 치수가 아니라 **기하 제약**에서 나온다.
    #   홀 서벽의 루넷은 베이 경계(v = 홀 중심)에서 스프링잉 3.4 까지 내려오고
    #   베이 중앙에서 9.0 으로 올라간다. 전고 5.5 짜리 포털을 베이 경계에 두면
    #   **볼트를 뚫는다.** 베이 중앙(홀 안목 끝에서 5.6 m)에 놓아야 머리가 뜬다.
    #   르네상스 계획에서 주 포털을 볼트 베이에 정렬하는 것과도 맞는다.
    'portal_at_bay_centre': (1.0, '베이 경계에 두면 루넷 스프링잉 3.4 < 전고 5.5 '
                                  '라 볼트를 뚫는다. Табл.12 평면에 포털 표시가 '
                                  '없어 좌우 중 어느 베이인지는 미확정', 'derived'),
    # ⚠ подклет 은 **통짜로 둔다.** Табл.12 에 하층 평면이 없다.
    #   근거 없이 방을 지어내지 않는다. 진입은 붉은 계단 → сени 로 한다.
    'podklet_plan_missing': (0.0, 'Табл.12 에 하층 평면 없음. 지어내지 말 것',
                             'counted'),
}

BKD = {   # Большой Кремлёвский дворец — 대크렘린궁, 1838–49, К.А. Тон
    'facade_len': (125.0, 'ru.wiki', 'measured'),
    'height': (47.0, 'ru.wiki', 'measured'),
    'floor_area': (25000.0, 'ru.wiki 약 25,000 m²', 'measured'),
    'rooms': (700, 'ru.wiki 약 700실', 'counted'),
    # 주 파사드에 창이 3열. 상층 대홀 창이 2단이라 밖에서는 3층으로 보이지만
    # 실제 상층은 1개 층이다 — 층수와 창 열을 혼동하면 비례가 통째로 틀어진다.
    'window_rows': (3, 'ru.wiki 「три ряда окон」', 'counted'),
    'built': (1849, 'ru.wiki', 'measured'),
    # ❌ 창 개수 미확보.
    'depth': (60.0, '평면 비례 추정', 'derived'),
}

SENAT = {   # Сенатский дворец — 상원궁, 1776–87, Казаков
    'rotunda_dia': (24.6, 'en.wiki 「Kremlin Senate」. 24 m 로 인용되기도 함',
                    'measured'),
    'plan': ('triangle', 'ru/en wiki. 이등변삼각형, 모서리 절단, 중정 3개',
             'measured'),
    'built': (1787, 'en.wiki', 'measured'),
    'dome_green': (True, '녹색 돔 + 정상부 국기 게양대', 'measured'),
}

ARSENAL = {   # Арсенал, 1701–36
    'wall_thick': (sazhen(0, 4), 'ru.wiki 「4 아르신」 = 2.845 m', 'measured'),
    'floors': (2, 'ru.wiki', 'counted'),
    'built': (1736, 'ru.wiki', 'measured'),
    # ❌ 파사드 길이·높이 미확보. OSM relation 51497 에 height=24, 2층이 있다.
    'height': (24.0, 'OSM relation 51497 height 태그', 'measured'),
}

GKD = {   # Государственный Кремлёвский дворец, 1961
    'length': (120.0, 'ru.wiki', 'measured'),
    'width': (70.0, 'ru.wiki', 'measured'),
    'floors': (6, 'ru.wiki', 'counted'),
    'depth_below': (15.0, 'ru.wiki. 건물의 큰 부분이 지하', 'measured'),
    'seats': (6000, 'ru.wiki 대회의장', 'counted'),
    'built': (1961, 'ru.wiki', 'measured'),
    # ❌ 지상 높이 미확정. 주변 역사 건물에 맞춰 억제 설계됐다.
    'height': (29.0, 'ru.wiki 「주변 높이에 맞춰 억제」 + 6층에서 추정', 'derived'),
}

# ---------------------------------------------------------------- 전시물

TSAR_CANNON = {
    'barrel_len': (5.34, 'en.wiki', 'measured'),
    'bore': (0.890, 'en.wiki 890 mm', 'measured'),
    'outer_dia': (1.200, 'en.wiki', 'measured'),
    'mass_kg': (39312.0, 'en.wiki', 'measured'),
    'cast': (1586, 'Андрей Чохов', 'measured'),
}

TSAR_BELL = {
    'height': (6.14, 'en.wiki', 'measured'),
    'diameter': (6.60, 'en.wiki', 'measured'),
    'wall_thick': (0.61, 'en.wiki 최대 61 cm', 'measured'),
    'mass_kg': (201924.0, 'en.wiki', 'measured'),
    'fragment_kg': (11500.0, 'en.wiki. 1737 화재 시 파손된 조각', 'measured'),
    'cast': (1735, 'Иван + Михаил Моторин', 'measured'),
}

# ---------------------------------------------------------------- 붉은광장

RED_SQUARE = {
    'length': (330.0, 'ru/en wiki 전 출처 일치', 'measured'),
    'width': (70.0, 'ru/en wiki', 'measured'),
    # ⚠ en.wiki 는 면적을 73,000 m² 로 적는데 330×70 = 23,100 과 모순이다.
    #   산술이 맞는 러시아어 출처를 따른다.
    'area': (23100.0, 'ru 출처 23,100 m² (330×70 과 일치). '
                      'en.wiki 의 73,000 m² 는 상충', 'measured'),
}

ST_BASIL = {   # Собор Василия Блаженного — 크렘린 밖, 붉은광장 남단
    # ⚠ 65 m / 47.5 m 두 값이 유통되고 OSM 은 67 m 다. 65 m 가 십자가 포함
    #   총고, 47 m 가 중앙 텐트 높이로 보인다.
    'height': (65.0, 'en/ru wiki 다수. OSM rel 3030568 은 67, 일부 자료는 47.5',
               'measured'),
    'height_central': (47.0, '중앙 돔(텐트) 높이', 'measured'),
    'width': (38.0, 'en.wiki 약 38 m', 'measured'),
    'area': (1500.0, 'en.wiki', 'measured'),
    'domes': (10, '8개가 중앙 9번째 교회를 둘러싸고, 10번째는 1588 증축',
              'counted'),
    'built': (1561, 'en.wiki', 'measured'),
}

GUM = {
    'facade_len': (242.0, 'en.wiki. 붉은광장 면 정면', 'measured'),
    'length': (250.0, 'en.wiki 전체', 'measured'),
    'width': (90.0, 'en.wiki', 'measured'),
    'floors': (3, 'en.wiki', 'counted'),
    'built': (1893, 'Померанцев(건축) + Шухов(구조)', 'measured'),
}

LENIN_MAUSOLEUM = {
    'facade_len': (24.0, '다수 출처', 'measured'),
    'height': (12.0, '다수 출처', 'measured'),
    'steps': (5, '「пять уступов различной высоты」', 'counted'),
    'built': (1930, 'Щусев. 화강암 2,900 m²', 'measured'),
}

HISTORICAL_MUSEUM = {
    'built': (1883, 'Шервуд + Семёнов. 신러시아 양식', 'measured'),
    'floors': (3, 'OSM relation 5963922 building:levels', 'measured'),
    # ❌ **치수를 어느 출처에서도 못 구했다.** OSM 폴리곤에서 재야 한다.
}

# 매립된 해자. 붉은광장 포장에 흔적을 넣을지는 선택이다.
ALEVIZ_MOAT = {
    'length': (541.0, 'ru.wiki 「Алевизов ров」', 'measured'),
    'width_min': (28.0, 'ru.wiki', 'measured'),
    'width_max': (34.0, 'ru.wiki', 'measured'),
    'depth_min': (8.5, 'ru.wiki', 'measured'),
    'depth_max': (13.0, 'ru.wiki', 'measured'),
    'filled': (1814, 'ru.wiki 1813–14 매립', 'measured'),
}

# ---------------------------------------------------------------- 양파돔
#
# ⚠ **이 비율들은 전부 derived 다.** 핵심 정의(돔 최대 직경 > 드럼 직경,
#   높이 > 폭)는 en.wikipedia 「Onion dome」에 있지만, 아래 황금비 수치는
#   Grokipedia 등 2차/AI 백과에서 나온 것이고 en.wiki 본문에는 없다.
#   → 스케치팹 Onion Dome (a13043fdbf3e46419816c58108e0ef11, CC BY-NC) 의
#     메시 단면과 대조하고, 실루엣 렌더로 사진 검증한 뒤 measured 로 승격한다.
# ⚠⚠ **2차 출처의 세 수치는 서로 모순이다.** 직접 계산해서 확인했다:
#     h/w = 1.5~2.0 이라면서, 동시에 드럼경:최대폭 = 1:1.382 이고
#     드럼경:높이 = 1:1.618 이라고 한다. 그런데 뒤의 둘에서
#         h/w = 1.618 / 1.382 = **1.171**
#     이 나온다. 1.5~2.0 과 양립하지 않는다.
#   → 자기정합적인 **bulge_ratio·height_ratio 쌍을 채택**한다. 사진과도
#     이쪽이 맞다 — 우스펜스키·아르한겔스키의 돔은 폭과 높이가 엇비슷하고,
#     h/w 가 1.5 를 넘는 길쭉한 돔은 성 바실리의 텐트형에 가깝지 양파돔이 아니다.
#     h_over_w_* 는 참고로만 남긴다.
DOME = {
    'bulge_ratio': (1.382, '드럼 직경 : 돔 최대폭 = 1 : 1.382', 'derived'),
    'height_ratio': (1.618, '드럼 직경 : 돔 높이 = 1 : 1.618 (황금비)', 'derived'),
    'h_over_w': (1.618 / 1.382, 'height_ratio / bulge_ratio = 1.171', 'derived'),
    # ⚠ 아래 둘은 위와 모순되는 2차 출처 값이다. **쓰지 않는다.**
    'h_over_w_cited_min': (1.5, 'Grokipedia — bulge/height 비와 모순', 'derived'),
    'h_over_w_cited_max': (2.0, '위와 같음', 'derived'),
    # 벌징 정점이 전체 높이의 어디쯤인가. 실루엣을 좌우하는 값이다.
    'bulge_z': (0.35, '사진 비례 추정', 'derived'),
    'neck_ratio': (1.05, '드럼 바로 위에서 살짝 오목해졌다가 벌어진다', 'derived'),
}

# 돔 개수의 상징. 배치 규칙이므로 형태 문법에 직접 걸린다.
DOME_SYMBOLISM = {
    1: '그리스도', 3: '삼위일체', 5: '그리스도 + 4복음사가',
    9: '천사 9계급', 13: '그리스도 + 12사도', 33: '그리스도의 생애',
}


# ---------------------------------------------------------------- 접근자


def val(d, k):
    """(값, 출처, 신뢰도) 에서 값만."""
    return d[k][0]


def get(d, k, fallback=None):
    """(값, 신뢰도). 없으면 (fallback, 'missing')."""
    if k not in d:
        return (fallback, 'missing')
    return (d[k][0], d[k][2])


def tower(name, k):
    """탑 속성. 상충 2건은 height 를 derived 로 낮춰 돌려준다."""
    t = TOWERS[name]
    conf = TOWER_COLUMNS.get(k, (None, 'derived'))[1]
    if k == 'height' and name in TOWER_CONFLICT:
        conf = 'derived'
    return (t[k], conf)


def report(name, d):
    """신뢰도 분포를 찍는다. derived 가 많으면 그게 곧 할 일 목록이다."""
    from collections import Counter
    c = Counter(v[2] for v in d.values() if isinstance(v, tuple) and len(v) == 3)
    print("  %-22s %s" % (name, dict(c)))
    return c


def report_all():
    from collections import Counter
    tables = [
        ('WALL', WALL), ('MERLON', MERLON), ('STAR_SPEC', STAR_SPEC),
        ('USPENSKY', USPENSKY), ('ARKHANGELSKY', ARKHANGELSKY),
        ('BLAGOVESHCHENSKY', BLAGOVESHCHENSKY), ('IVAN_BELL', IVAN_BELL),
        ('GRANOVITAYA', GRANOVITAYA), ('BKD', BKD), ('SENAT', SENAT),
        ('ARSENAL', ARSENAL), ('GKD', GKD),
        ('TSAR_CANNON', TSAR_CANNON), ('TSAR_BELL', TSAR_BELL),
        ('RED_SQUARE', RED_SQUARE), ('ST_BASIL', ST_BASIL), ('GUM', GUM),
        ('LENIN_MAUSOLEUM', LENIN_MAUSOLEUM), ('DOME', DOME),
    ]
    tot = Counter()
    print("크렘린 치수표 신뢰도")
    for nm, d in tables:
        tot += report(nm, d)
    # 탑은 열 단위로 신뢰도가 붙는다
    tconf = Counter()
    for nm in TOWERS:
        for k in ('year', 'height', 'x', 'y', 'w', 'd', 'yaw', 'shape'):
            tconf[tower(nm, k)[1]] += 1
    print("  %-22s %s" % ('TOWERS (20기)', dict(tconf)))
    tot += tconf
    print("  " + "-" * 46)
    print("  %-22s %s" % ('합계', dict(tot)))
    n = sum(tot.values())
    print("  measured 비율 %.0f%%  (derived %d 건이 남은 할 일)"
          % (100.0 * tot['measured'] / n, tot['derived']))
    return tot
