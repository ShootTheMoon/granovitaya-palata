# -*- coding: utf-8 -*-
"""Hunyuan3D 생성 FBX 6개를 사이트 좌표에 세워 기존 절차 생성 매싱과 대조한다.

임포트 방향 주의 — `bpy.ops.import_scene.fbx` 는 FBX Z-up 을 처리하려고
오브젝트에 **X +90° 를 걸어서** 들여온다. 이관 명세서의 "X −90° 적용"은
그 회전이 안 걸리는 임포트 설정을 전제한 말이라, 여기서는 되돌리면 안 되고
**적용해야** 한다. 되돌리면 우스펜스키 평면비가 1.00 으로 뭉개진다
(옳게 적용하면 1.453 이고, 명세서 §3 의 "평면비 1.45" 와 맞는다).

`ob.dimensions` 는 회전을 반영하지 않는다는 점도 같이 걸린다. 방향 판정은
dimensions 가 아니라 회전을 적용한 뒤의 bound_box 로 해야 한다.
"""

import os
import math

import bpy
from mathutils import Vector

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models_hunyuan")

# 검토용 컬렉션. sites.KRM['collections'] 에 등록하지 않았으므로 group_of 가
# 그룹을 못 잡아 오버데어 익스포터가 알아서 건너뛴다.
COLL = "크렘린_HY_검토"

# 0 이다. `sites.KRM["origin_m"]` 의 1800 m 는 **오버데어 레벨 좌표**를 위한
# 값이고 (make_placement.py 가 익스포트 단계에서 쓴다), .blend 는 OSM 로컬
# 좌표 그대로 서 있다. 절차 생성 종탑이 (5.7, -100.2) 로 README 의
# (5.65, -100.19) 와 같다는 것이 그 증거다. 1800 을 걸면 매싱에서
# 1.8 km 동쪽에 떨어져 선다.
ORIGIN_X = 0.0

# (파일, 이름, x, y, yaw°, 실전고 m, 실측평면 장×단 m)
#   좌표·치수 출처: ref/README.md (OSM 실측), 성바실리만 이관명세서 §5
TABLE = [
    ("01_성바실리대성당_프롬프트_텍스처완성_★최고품질.fbx",
     "HY_01_성바실리",     312.28,   94.42, 34.0, 67.0, (52.01, 46.63)),
    ("02_우스펜스키대성당_프롬프트2차_텍스처.fbx",
     "HY_02_우스펜스키",   -66.58,  -76.79, 16.0, 49.0, (43.10, 28.62)),
    ("03_블라고베셴스키대성당_프롬프트_텍스처.fbx",
     "HY_03_블라고베셴스키", -77.74, -179.25, 14.0, 37.0, (26.59, 23.21)),
    ("04_이반대제종탑_프롬프트_파고다오류_텍스처없음.fbx",
     "HY_04_이반대제종탑",    5.65, -100.19, 19.0, 81.0, (14.88, 14.63)),
    ("05_스파스카야탑_이미지기반_원본_정리필요.fbx",
     "HY_05_스파스카야",    204.77,  100.55, 47.0, 71.0, (25.59, 18.03)),
    # 대크렘린궁이 아니라 일반 유럽 궁전이다. 제자리가 없으니 남쪽 빈터에 둔다.
    ("99_유럽풍궁전_대크렘린궁시도실패작_범용소재.fbx",
     "HY_99_유럽풍궁전",      0.00, -520.00,  0.0, 47.0, None),
]


def _collection():
    col = bpy.data.collections.get(COLL)
    if col is None:
        col = bpy.data.collections.new(COLL)
        bpy.context.scene.collection.children.link(col)
    return col


def _bbox(ob):
    bb = [Vector(c) for c in ob.bound_box]
    lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
    hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
    return lo, hi


def place(row):
    """FBX 하나를 세워 배치하고 (이름, 실제평면, 실측평면) 을 돌려준다."""
    fn, name, x, y, yaw, height, plan = row

    old = bpy.data.objects.get(name)
    if old is not None:
        me = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if me.users == 0:
            bpy.data.meshes.remove(me)

    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=os.path.join(DIR, fn))
    new = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    if not new:
        raise RuntimeError("임포트 결과가 비었다: %s" % fn)

    bpy.ops.object.select_all(action='DESELECT')
    if len(new) > 1:                      # 조각나 있으면 합친다
        for o in new:
            o.select_set(True)
        bpy.context.view_layer.objects.active = new[0]
        bpy.ops.object.join()
        new = [bpy.context.view_layer.objects.active]

    ob = new[0]
    ob.name = name
    ob.data.name = name

    # 1) Z-up 회전을 적용해 로컬 Z 를 위로 굳힌다
    ob.location = (0.0, 0.0, 0.0)
    ob.scale = (1.0, 1.0, 1.0)
    ob.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # 2) 전고를 실측에 맞춰 균일 스케일, 바닥중심을 원점으로
    lo, hi = _bbox(ob)
    raw = hi - lo
    s = height / raw.z
    ob.scale = (s, s, s)
    ob.location = (-(lo.x + hi.x) * 0.5 * s,
                   -(lo.y + hi.y) * 0.5 * s,
                   -lo.z * s)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # 3) 사이트 좌표 배치. yaw 는 +X(동)에서 반시계로 잰 주축각이다.
    ob.location = (ORIGIN_X + x, y, 0.0)
    ob.rotation_euler = (0.0, 0.0, math.radians(yaw))

    col = _collection()
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    col.objects.link(ob)

    got = (raw.x * s, raw.y * s)
    return name, got, plan, len(ob.data.polygons)


def report(name, got, plan, faces):
    gl, gs = max(got), min(got)
    if plan is None:
        return "%-20s 평면 %5.1f x %5.1f   면 %8d   (대조 대상 아님)" % (
            name, got[0], got[1], faces)
    return ("%-20s 평면 %5.1f x %5.1f  실측 %5.1f x %5.1f  "
            "오차 %+6.1f%% /%+6.1f%%  비 %.3f vs %.3f  면 %8d" % (
                name, gl, gs, plan[0], plan[1],
                (gl / plan[0] - 1) * 100.0, (gs / plan[1] - 1) * 100.0,
                gl / gs, plan[0] / plan[1], faces))


def run(keys=None):
    """keys 는 파일명 앞 2자리 문자열 목록. 생략하면 전부."""
    out = []
    for row in TABLE:
        if keys is not None and row[0][:2] not in keys:
            continue
        out.append(report(*place(row)))
        print(out[-1])
    return out


# ------------------------------------------------------------------ OSM 정합

# 전고에 맞춰 균일 스케일하면 평면이 남는다. Hunyuan 이 단위 큐브로 정규화하면서
# 높이/평면 비를 못 지키기 때문이다. 실측 평면까지 맞추려면 축마다 따로 눌러야
# 한다 — 이관 명세서 §5 가 성바실리에 «X ×1.12 / Y ×1.24» 로 지시한 것과 같은
# 조작이고, 여기서는 배율을 손으로 적지 않고 OSM 발자국에서 매번 계산한다.
#
# 배치 좌표를 README 에서 읽지 않는 이유: README·명세서의 (x, y) 는 발자국의
# OBB 중심이 아니다. 성바실리에서 5.1 m 어긋났다. 모델 bbox 를 발자국 bbox 에
# 맞추는 조작이므로 기준도 발자국 bbox 중심이어야 한다.

SNAP = [
    # (오브젝트, OSM 종류, id, yaw°, 전고 m)
    ("HY_01_성바실리",     "relation", "3030568", 34.0, 67.0),
    ("HY_02_우스펜스키",    "relation", "3028585", 16.0, 49.0),
    ("HY_03_블라고베셴스키",  "relation", "1359251", 14.0, 37.0),
    # 명세서 §3 은 파고다 오류라 폐기 판정을 했지만, 실측 평면(14.88 x 14.63)
    # 에 맞춰 눌러 보면 5.4:1 로 홀쭉해지면서 처마가 거의 안 읽힌다.
    # 폐기하기 전에 이 상태를 먼저 보라 — 배율이 X x0.54 로 극단적이다.
    ("HY_04_이반대제종탑",   "relation", "1359281", 19.0, 81.0),
]


def _frame(pts2, deg):
    """건물 주축 기준 회전계에서 (중심x, 중심y, 폭, 깊이)."""
    a = math.radians(-deg)
    c, s = math.cos(a), math.sin(a)
    xs = [q[0] * c - q[1] * s for q in pts2]
    ys = [q[0] * s + q[1] * c for q in pts2]
    return ((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5,
            max(xs) - min(xs), max(ys) - min(ys))


def snap_to_osm(obj_name, kind, osm_id, yaw, height):
    """모델 bbox 를 OSM 발자국 bbox 에 맞춘다. 전고는 실측값을 지킨다."""
    import geo_kr

    o = geo_kr.load()
    feat = o.by_id(osm_id, kind=kind)
    if feat is None:
        raise RuntimeError("OSM %s %s 를 캐시에서 못 찾았다" % (kind, osm_id))
    pts = list(geo_kr.project(list(o.rings(feat))[0]))
    fcx, fcy, fw, fd = _frame(pts, yaw)

    ob = bpy.data.objects[obj_name]
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)

    lo, hi = _bbox(ob)                       # 로컬 — 회전 적용 후라 축이 정렬돼 있다
    raw = hi - lo
    sx, sy, sz = fw / raw.x, fd / raw.y, height / raw.z

    keep_rot = tuple(ob.rotation_euler)
    ob.location = (0.0, 0.0, 0.0)
    ob.rotation_euler = (0.0, 0.0, 0.0)
    ob.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    lo, hi = _bbox(ob)
    ob.location = (-(lo.x + hi.x) * 0.5, -(lo.y + hi.y) * 0.5, -lo.z)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

    # 발자국 bbox 중심으로. 회전계 좌표를 월드로 되돌린다.
    a = math.radians(yaw)
    ob.rotation_euler = keep_rot
    ob.location = (fcx * math.cos(a) - fcy * math.sin(a),
                   fcx * math.sin(a) + fcy * math.cos(a),
                   0.0)
    bpy.context.view_layer.update()

    mcx, mcy, mw, md = _frame(
        [(ob.matrix_world @ Vector(b)).to_2d()[:] for b in ob.bound_box], yaw)
    return ("%-20s 배율 X x%.4f Y x%.4f Z x%.4f  ->  %.2f x %.2f x %.2f  "
            "(발자국 %.2f x %.2f)  중심오차 %.3f m" % (
                obj_name, sx, sy, sz, mw, md, height, fw, fd,
                math.hypot(mcx - fcx, mcy - fcy)))


def snap_all():
    out = []
    for row in SNAP:
        if bpy.data.objects.get(row[0]) is None:
            continue
        out.append(snap_to_osm(*row))
        print(out[-1])
    return out
