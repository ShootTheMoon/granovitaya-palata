# -*- coding: utf-8 -*-
"""Hunyuan3D 로 뽑은 실내 소품을 파세트궁 실내 좌표에 앉힌다.

`hy_import.place()` 가 건물용으로 만든 절차를 소품용으로 일반화한 것이다.
**복제가 아니라 일반화다** — 건물과 다른 점이 셋뿐이라 그것만 바꿨다.

    건물 (hy_import)              소품 (여기)
    ────────────────────────────────────────────────────
    전고(height)로 균일 스케일  →  세 변을 실측 상자에 맞춰 **비균일** 스케일
    바닥중심을 원점             →  같음 (유지)
    월드 (x, y) 에 직접 배치     →  같음 (실내는 yaw 0 이라 변환이 없다)
    데시메이트 없음             →  **임포트 직후 필수**

★ 반드시 유지할 것 (`hy_import` 도크스트링에 이유가 있다)
  · `bpy.ops.import_scene.fbx` 는 FBX Z-up 을 처리하려고 오브젝트에 **X +90°**
    를 걸어서 들여온다. 이관 명세서의 「X −90° 적용」은 그 회전이 안 걸리는
    임포트 설정을 전제한 말이라, 여기서는 되돌리면 안 되고 **적용해야** 한다.
    되돌리면 우스펜스키 평면비가 1.45 → 1.00 으로 뭉개졌다.
  · 방향 판정은 `ob.dimensions` 가 아니라 **회전을 적용한 뒤의 `bound_box`** 다.

⚠ 아래 치수는 전부 **derived** 다. Табл.14·15 는 사진이라 축척자가 없고,
  앵커가 중앙 기둥 2.3 m 와 문 손잡이 1.0 m 뿐이다. ±20% 로 보고 놓아 본 뒤
  눈으로 맞춘다 — 그래서 `place()` 가 `size` 를 인자로 받는다.
"""

import math
import os

import bpy
from mathutils import Vector

import hanok
import kremlin.interior as interior

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "models_hunyuan", "interior")

COLL = interior.COLL['prop']          # "파세트실내_소품"

# 반출본 예산. 소품 하나가 1.5M 면으로 들어온다 — 방 전체가 3만 삼각형이다.
# 스파스카야에서 1.49M vs 200k vs 50k vs 20k 를 근접 렌더로 비교해 육안 차이가
# 없었다는 기록이 있다.
FACE_RENDER = 30000
FACE_EXPORT = 6000


def _bbox_local(ob):
    bb = [Vector(c) for c in ob.bound_box]
    lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
    hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
    return lo, hi


def _decimate(ob, target):
    """면수를 target 이하로. 이미 그 아래면 아무것도 안 한다."""
    n = len(ob.data.polygons)
    if n <= target:
        return n
    m = ob.modifiers.new("DEC", 'DECIMATE')
    m.ratio = float(target) / float(n)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=m.name)
    return len(ob.data.polygons)


def place(filename, name, size, loc, yaw=0.0, mat=None, faces=FACE_RENDER,
          anchor='bottom'):
    """FBX 하나를 임포트해 실측 상자에 맞춰 놓는다.

    `size` = (폭 x, 깊이 y, 높이 z) m. `loc` 은 앵커 지점의 월드 좌표다.
    `anchor` 가 'bottom' 이면 바닥중심, 'top' 이면 윗면중심(샹들리에용).
    """
    path = os.path.join(DIR, filename)
    if not os.path.exists(path):
        return None, "파일 없음: %s" % path

    old = bpy.data.objects.get(name)
    if old is not None:
        me = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if me and me.users == 0:
            bpy.data.meshes.remove(me)

    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    if not new:
        return None, "임포트 결과가 비었다: %s" % filename

    bpy.ops.object.select_all(action='DESELECT')
    if len(new) > 1:                      # 조각나 있으면 합친다
        for o in new:
            o.select_set(True)
        bpy.context.view_layer.objects.active = new[0]
        bpy.ops.object.join()
        new = [bpy.context.view_layer.objects.active]
    ob = new[0]
    ob.name = ob.data.name = name

    # 1) Z-up 회전을 **적용해** 로컬 Z 를 위로 굳힌다
    ob.location = (0.0, 0.0, 0.0)
    ob.scale = (1.0, 1.0, 1.0)
    ob.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    n0 = len(ob.data.polygons)
    n1 = _decimate(ob, faces)

    # 2) 실측 상자에 맞춰 **비균일** 스케일 + 앵커를 원점으로
    lo, hi = _bbox_local(ob)
    raw = hi - lo
    sx = size[0] / max(1e-6, raw.x)
    sy = size[1] / max(1e-6, raw.y)
    sz = size[2] / max(1e-6, raw.z)
    ob.scale = (sx, sy, sz)
    zref = lo.z if anchor == 'bottom' else hi.z
    ob.location = (-(lo.x + hi.x) * 0.5 * sx,
                   -(lo.y + hi.y) * 0.5 * sy,
                   -zref * sz)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # 3) 배치
    ob.location = loc
    ob.rotation_euler = (0.0, 0.0, math.radians(yaw))

    if mat:
        ob.data.materials.clear()
        ob.data.materials.append(hanok.get_mat(mat))

    col = hanok.new_collection(COLL)
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    col.objects.link(ob)
    return ob, "%-16s %7d → %6d면  %.2f×%.2f×%.2f m" % (
        name, n0, n1, size[0], size[1], size[2])


def table(site=None, pod=None):
    """(파일, 이름, size, loc, yaw, anchor) 목록. 방 좌표에서 계산한다.

    상수를 손으로 적지 않는다 — `interior.Site` 가 치수의 유일한 출처다.
    """
    site = site or interior.Site()
    portal = interior.portal_rect(site, 0)
    pv = (portal[0] + portal[1]) / 2.0
    dado = interior.val(interior.measured.GRANOVITAYA, 'dado_h')
    g = interior.measured.GRANOVITAYA

    rows = [
        # поставец — 중앙 기둥을 감싼다. 바닥에 앉는다.
        ("I02_포스타베츠.fbx", "SP_포스타베츠", (4.30, 4.30, 2.75),
         (site.hcu, site.hcv, 0.0), 0.0, 'bottom'),
        # 옥좌 — 서벽 앞, 포털 반대쪽 베이 중앙. 다도 위에 얹는다.
        ("I01_옥좌.fbx", "SP_옥좌", (2.60, 2.00, 4.20),
         (site.hu0 + 1.3, site.hv0 + site.hall * 0.75, dado), 90.0, 'bottom'),
        # 조각 포털 틀 — 격벽 홀 쪽 면에 붙인다.
        # ⚠ 격벽은 u 축에 수직이다. 틀의 **폭(3.30)은 v**, 두께(0.40)가 u 다.
        #   (폭, 두께) 를 (x, y) 로 적으면 틀이 벽을 뚫고 홀로 3.3 m 튀어나온다.
        ("I03_포털틀.fbx", "SP_포털틀",
         (0.40, interior.val(g, 'portal_frame_w'),
          interior.val(g, 'portal_frame_h')),
         (site.hu0 + 0.20, pv, 0.0), 0.0, 'bottom'),
    ]
    # 판카딜로 4개 — 볼트 베이 중앙에 매단다. 윗면 기준이라 anchor='top'.
    q = site.hall / 4.0
    for i, (du, dv) in enumerate(((-q, -q), (q, -q), (-q, q), (q, q))):
        rows.append(("I04_판카딜로.fbx", "SP_판카딜로_%d" % i, (1.60, 1.60, 1.20),
                     (site.hcu + du, site.hcv + dv, 5.70), 0.0, 'top'))
    return rows


def run(faces=FACE_RENDER):
    """`models_hunyuan/interior/` 에 있는 것만 골라 전부 앉힌다."""
    out = []
    for fn, name, size, loc, yaw, anchor in table():
        ob, msg = place(fn, name, size, loc, yaw=yaw, faces=faces, anchor=anchor)
        out.append(msg)
        print(("  " if ob else "  ✗ ") + msg)
    return out


def check_fit():
    """놓인 소품이 홀 안목 안에 드는지, 볼트를 뚫지 않는지 수치로 확인한다.

    ⚠ 렌더로 보지 마라. 벽을 뚫은 적이 세 번 있고 전부 눈으로는 안 보였다.
    """
    site = interior.Site()
    bpy.context.view_layer.update()
    rows = []
    for ob in bpy.data.objects:
        if not ob.name.startswith("SP_"):
            continue
        bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
        hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
        bad = []
        if lo.x < site.hu0 - 1e-3 or hi.x > site.hu1 + 1e-3:
            bad.append("u 벗어남")
        if lo.y < site.hv0 - 1e-3 or hi.y > site.hv1 + 1e-3:
            bad.append("v 벗어남")
        if hi.z > site.crown + 1e-3:
            bad.append("볼트 마루 위")
        rows.append("%-16s x %6.2f~%6.2f  y %6.2f~%6.2f  z %5.2f~%5.2f  %s" % (
            ob.name, lo.x, hi.x, lo.y, hi.y, lo.z, hi.z,
            ", ".join(bad) if bad else "OK"))
        print("  " + rows[-1])
    return rows
