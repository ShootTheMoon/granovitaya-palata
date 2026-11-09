# -*- coding: utf-8 -*-
"""크렘린 + 붉은광장 전체 빌드.

`__init__.py` 가 이 파일을 설명해 놓고 정작 파일이 없어서 절차 생성 재빌드가
안 돌았다. 개별 빌더(`wall` · `tower` · `cathedral` · `palace` · `redsquare`)는
전부 멀쩡했고 없던 것은 그것들을 묶는 층뿐이다.

⚠ **조용한 병합 주의.** `hanok.new_collection()` 은 같은 이름이 있으면 기존
컬렉션을 그대로 돌려준다. 이미 지어진 씬에서 `build_all()` 을 그냥 부르면
같은 컬렉션에 지오메트리가 한 벌 더 쌓인다. 그래서 기본값은 **거부**다 —
비어 있지 않으면 `purge=True` 를 명시해야 지운다. 작업규칙 「블렌더 임포트
전에 씬을 지우지 마라」를 코드로 강제하는 셈이다.

purge 는 **관리 대상 컬렉션만** 비운다. 손으로 넣은 것(`크렘린_NC_*` ·
`크렘린_HY_*` · 카메라 · 라이트)은 건드리지 않는다.

    from kremlin import build_kr
    build_kr.build_all()                 # 빈 파일에서
    build_kr.build_all(purge=True)       # 다시 지을 때
"""

import bpy

from kremlin import (cathedral, dome, granovitaya, material, palace, redsquare,
                     tower, wall)

# 이 모듈이 만들고 책임지는 컬렉션. purge 대상도 정확히 이 목록이다.
# 여기 없는 컬렉션은 손대지 않는다 — 특히 크렘린_NC_스파스카야(라이선스
# 격리)와 크렘린_HY_검토(Hunyuan 생성본)는 절차 생성물이 아니다.
MANAGED = (
    "크렘린_성벽",
    "크렘린_여장",
    "크렘린_탑",
    "크렘린_성당",
    "크렘린_종탑",
    "크렘린_궁전",
    "크렘린_파세트궁",
    "크렘린_파세트궁_바닥",
    "붉은광장_포장",
    "붉은광장_건물",
    "붉은광장_성바실리",
)

# 돔 견본은 형태 문법을 눈으로 확인하는 용도라 기본 빌드에서 뺀다.
SAMPLE = "크렘린_돔_견본"


def occupied():
    """관리 대상 중 이미 오브젝트가 든 컬렉션 이름 목록."""
    out = []
    for name in MANAGED:
        coll = bpy.data.collections.get(name)
        if coll is not None and len(coll.objects):
            out.append(name)
    return out


def purge_managed():
    """관리 대상 컬렉션의 오브젝트만 지운다. 컬렉션 자체는 남긴다."""
    n = 0
    for name in MANAGED:
        coll = bpy.data.collections.get(name)
        if coll is None:
            continue
        for ob in list(coll.objects):
            me = ob.data if ob.type == 'MESH' else None
            bpy.data.objects.remove(ob, do_unlink=True)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
            n += 1
    return n


def build_all(purge=False, materials=True, world=True,
              skip_towers=(), samples=False):
    """전체를 짓고 검산 dict 를 돌려준다.

    purge      이미 지어져 있으면 관리 대상만 비우고 다시 짓는다.
               False 인 채로 비어 있지 않으면 RuntimeError 를 낸다.
    materials  material.apply() 까지 돌린다.
    world      HDRI 월드를 세운다.
    skip_towers  tower.build(skip=...) 로 넘긴다.
    samples    크렘린_돔_견본을 같이 만든다.
    """
    busy = occupied()
    if busy:
        if not purge:
            raise RuntimeError(
                "이미 지어져 있다: %s. 겹쳐 쌓이는 것을 막으려고 멈춘다. "
                "다시 지으려면 build_all(purge=True)." % ", ".join(busy))
        removed = purge_managed()
    else:
        removed = 0

    report = {"purged": removed}

    path, info = wall.wall_path()
    wall.build(path=path)
    report["wall"] = info

    tower.build(skip=skip_towers)
    cathedral.build()
    palace.build()
    # 파세트궁은 palace.PALACES 에 없다 — OSM relation 이 따로고(7679578)
    # 실내까지 짓기 때문에 전용 모듈이다.
    report["granovitaya"] = granovitaya.build()
    redsquare.build()
    if samples:
        dome.build_test()

    if materials:
        material.apply()
    if world:
        material.setup_world()

    report["objects"] = len(bpy.data.objects)
    report["faces"] = sum(len(o.data.polygons)
                          for o in bpy.data.objects if o.type == 'MESH')
    return report
