# -*- coding: utf-8 -*-
"""경복궁 → OVERDARE Studio 익스포터.

헤드리스 실행:
    blender.exe -b --factory-startup -P export_overdare.py -- --calibrate --out <dir>
    blender.exe -b <blend>           -P export_overdare.py -- --export    --out <dir>

────────────────────────────────────────────────────────────────────────
좌표 규약 — Phase 0 에서 **측정으로 확정** (추정 아님)

  축 순열 : Blender (x, y, z) → OVERDARE (X, Z, Y)
            CAL 막대의 UnitExtent 로 확인. 4m→X400, 6m→Z600, 8m→Y800.
  단위     : ×100 (1 Blender m = 100 OVERDARE unit = 1 cm)
  피벗     : 임포터가 **각 메시를 자기 bbox 로 재중심화한다.**
            → 파일 원점 기준 오프셋은 사라진다. 그래서 월드 좌표를 굽고
              CFrame 0 에 놓는 방식은 못 쓴다. 대신 메시마다 **월드 bbox
              중심**을 계산해 CFrame.Position 에 넣는다.
  Z 부호   : Z = −(Blender y).  오버데어는 −Z 가 forward, Blender 는 +Y 가 북.

  X = bx * 100
  Y = bz * 100 + FLOOR_Y
  Z = -by * 100

이 방식의 이점: **Orientation 이 항상 0 이다.** 회전을 틀릴 방법이 없다.
대가: 기하가 같아도 인스턴싱을 못 한다(동서 회랑이 각각 별도 메시).
────────────────────────────────────────────────────────────────────────
"""

import bpy
import bmesh
import hashlib
import json
import math
import os
import sys
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sites                                                    # noqa: E402

# 상한은 **파일당** 30,000 이다 (2026-08-10 실측).
#   SJJ_01.fbx (16메시 / 51,816 삼각형) 임포트 거부:
#   "The imported model file exceeds the maximum allowed polygons.
#    Maximum allowed polygon count: 30,000"
# 에러가 '폴리곤'이라고 하므로, 삼각화하지 않으면 쿼드 1개가 1폴리곤으로
# 세어져 예산이 두 배가 될 수 있다. 건축은 전부 쿼드라 이득이 크다.
# 쿼드 실험 결과(2026-08-10): 25,460 폴리곤 / 51,816 삼각형짜리 쿼드 파일은
# **거부**됐고, 삼각형 3만 이하로 쪼갠 파일들은 통과했다.
# → 문구는 '폴리곤'이지만 실제로 세는 건 **삼각형**이다. 삼각화가 정답이다.
CAP = 30000               # 파일당 삼각형
CM = 100.0
FLOOR_Y = 5000.0          # 위층 플랫폼 상면 (cm)
TRIANGULATE = True


# ------------------------------------------------------------------ 유틸


def argv_after_dashdash():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def get_arg(args, name, default=None):
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return default


def has_flag(args, name):
    return name in args


def to_ovdr(v):
    """Blender 월드 좌표(m) → OVERDARE 좌표(cm)."""
    return (v.x * CM, v.z * CM + FLOOR_Y, -v.y * CM)


def to_ovdr_size(size_m):
    """Blender 월드 bbox 크기(m) → OVERDARE Size(cm). 축 순열만 적용, 부호 없음."""
    return (abs(size_m.x) * CM, abs(size_m.z) * CM, abs(size_m.y) * CM)


def srgb255(lin):
    """Blender 선형 색 → sRGB 0-255."""
    out = []
    for c in lin[:3]:
        s = 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055
        out.append(int(round(max(0.0, min(1.0, s)) * 255)))
    return out


# ------------------------------------------------------------ 슬러그

TOKENS = [
    ("근정전", "GJJ"), ("사정전", "SJJ"), ("근정문", "GJM"), ("사정문", "SJM"),
    ("회랑", "COR"), ("담장", "WAL"), ("모서리", "CNR"), ("조정", "CYD"),
    ("유물", "ART"), ("품계석", "RANKSTONE"),
    ("하월대", "WOLDAE_LO"), ("상월대", "WOLDAE_UP"),
    ("일월오봉도", "SCREEN"), ("어좌", "THRONE"), ("향로", "CENSER"),
    ("등롱", "LANTERN"), ("서안", "DESK"),
    ("지붕면", "ROOF"), ("수키와", "RIB"), ("서까래", "RAFTER"),
    ("합각", "GABLE"), ("박공", "GABLEND"), ("마루", "MARU"),
    ("초석", "BASE"), ("고주", "HICOL"), ("기둥", "COL"),
    ("창방", "BEAM"), ("공포", "BRACKET"), ("소로", "BLOCK"),
    ("창호지", "PAPER"), ("창살", "LATTICE"), ("인방", "FRAME"),
    ("화방벽", "WALLSTONE"), ("회벽", "WALLPLAS"), ("사고석", "WALLBASE"),
    ("기와갓", "WALLCAP"), ("난간", "BALUS"), ("계단", "STAIR"),
    ("답도", "DAPDO"), ("기단", "PLAT"), ("박석", "PAVE"), ("어도", "PATH"),
    ("지면", "GROUND"), ("벽", "WALLP"),
    ("하층", "LO"), ("상층", "UP"),
    ("동", "E"), ("서", "W"), ("남", "S"), ("북", "N"),
]


def slug_for(name):
    """한글 오브젝트명 → 충돌 없는 ASCII 슬러그.

    해시를 붙이는 이유: '마루' 가 마룻바닥(근정전_마루)과 지붕마루
    (근정전_상층_마루) 를 동시에 뜻해 의미 변환만으로는 구분이 안 된다.
    """
    s = name
    for ko, en in TOKENS:
        s = s.replace(ko, "_" + en + "_")
    out = []
    for ch in s:
        out.append(ch if (ch.isascii() and (ch.isalnum() or ch == "_")) else "_")
    s = "".join(out)
    while "__" in s:
        s = s.replace("__", "_")
    s = s.strip("_")[:40]
    h = hashlib.sha1(name.encode("utf-8")).hexdigest()[:6]
    return "%s_%s" % (s, h) if s else "OBJ_%s" % h


# ------------------------------------------------------- 메시 추출/분할


def evaluated_world_mesh(obj, depsgraph):
    """모디파이어를 적용하고 matrix_world 를 구운 새 메시를 만든다.

    loc/rot/scale 이 아니라 matrix_world 를 쓰는 게 핵심이다 —
    유물 부모 EMPTY 의 0.44045 스케일과 180° yaw 가 여기에만 담겨 있다.
    """
    ev = obj.evaluated_get(depsgraph)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True,
                                         depsgraph=depsgraph)
    me.transform(obj.matrix_world)
    if obj.matrix_world.determinant() < 0:
        me.flip_normals()
    return me


def mesh_tris(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


def mesh_polys(me):
    return len(me.polygons)


def mesh_budget(me):
    """예산 계산에 쓰는 수. 삼각화하면 삼각형, 아니면 폴리곤."""
    return mesh_tris(me) if TRIANGULATE else mesh_polys(me)


def mesh_bbox(me):
    if not me.vertices:
        return Vector((0, 0, 0)), Vector((0, 0, 0))
    xs = [v.co for v in me.vertices]
    mn = Vector((min(v.x for v in xs), min(v.y for v in xs), min(v.z for v in xs)))
    mx = Vector((max(v.x for v in xs), max(v.y for v in xs), max(v.z for v in xs)))
    return mn, mx


def split_mesh_lossless(me, cap=CAP):
    """예산 상한을 넘는 메시를 면 단위로 쪼갠다. 정점/면을 새로 만들지 않는다.

    가장 긴 축으로 면 중심을 정렬한 뒤 균등 분할한다. 분할 조각들의
    면 수 합은 원본과 정확히 같아야 한다 (검증은 호출부에서).
    """
    total = mesh_budget(me)
    if total <= cap:
        return [me]

    k = int(math.ceil(total / float(cap)))
    mn, mx = mesh_bbox(me)
    ext = mx - mn
    axis = max(range(3), key=lambda i: ext[i])

    faces = []
    for p in me.polygons:
        c = sum((me.vertices[i].co for i in p.vertices), Vector()) / len(p.vertices)
        w = (len(p.vertices) - 2) if TRIANGULATE else 1
        faces.append((c[axis], p.index, w))
    faces.sort(key=lambda t: t[0])

    per = total / float(k)
    groups, cur, acc, target = [], [], 0, per
    for _, pidx, tris in faces:
        cur.append(pidx)
        acc += tris
        if acc >= target and len(groups) < k - 1:
            groups.append(cur)
            cur, acc = [], 0
    groups.append(cur)

    out = []
    for gi, pidxs in enumerate(groups):
        if not pidxs:
            continue
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        keep = set(pidxs)
        drop = [f for f in bm.faces if f.index not in keep]
        bmesh.ops.delete(bm, geom=drop, context='FACES')
        # context='FACES' 는 **면만 지우고 정점은 남긴다.** 그래서 조각마다
        # 원본 정점 전체를 이고 갔다 — 한옥(47만 정점)을 8조각으로 쪼갰더니
        # 조각 하나가 143 MB 가 됐다. 같은 오브젝트를 통째로 내보내면 6.4 MB 다.
        # 면이 안 붙은 정점만 지우므로 면 집합은 그대로고 무손실 검사도 통과한다.
        loose = [v for v in bm.verts if not v.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context='VERTS')
        nm = bpy.data.meshes.new("%s_p%02d" % (me.name, gi))
        # **머티리얼 슬롯을 옮긴다.** bm.to_mesh 는 면의 material_index 만
        # 쓰고 슬롯(nm.materials)은 안 옮긴다. 빠뜨리면 조각에 머티리얼이
        # 없어 FBX 에 텍스처가 하나도 안 실린다 — 화성 v19 에서 279개 중
        # 235개(도시 한옥 211 + 수목 15 + 화서문 3 + 가로수 3 + 방화수류정 3)가
        # 이것 때문에 회색으로 나갔다. 경복궁·덕수궁은 팔레트 단색이라
        # 텍스처가 없어 증상이 안 보였을 뿐 같은 버그를 지나왔다.
        #
        # **쓰는 것만 옮긴다.** 원본 슬롯을 통째로 복사했더니 사랑채 15종이
        # 189조각마다 실려 익스포트가 455 MB → 3.34 GB 가 됐다(같은 1024²
        # 텍스처가 189번 중복). 조각은 공간 슬라이스라 대개 2~3종만 쓴다.
        used = sorted({f.material_index for f in bm.faces})
        remap = {o: n for n, o in enumerate(used)}
        for f in bm.faces:
            f.material_index = remap[f.material_index]
        for oi in used:
            nm.materials.append(me.materials[oi] if oi < len(me.materials) else None)
        bm.to_mesh(nm)
        bm.free()
        out.append(nm)
    return out


# --------------------------------------------------------- 박스 추출

def extract_boxes(me, tol=1e-4):
    """메시가 축정렬 박스들의 모임이면 [(center, size), ...] 를, 아니면 None.

    조정 지면·담장처럼 순수 박스인 것은 네이티브 Part 로 바꾼다 —
    임포트 트립이 줄고 90×186m 지면에 제대로 된 박스 콜라이더가 생긴다.
    """
    if not me.polygons or len(me.polygons) % 6 != 0:
        return None
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()

    seen, boxes = set(), []
    for v in bm.verts:
        if v.index in seen:
            continue
        # 연결 성분 수집
        stack, comp = [v], set()
        while stack:
            w = stack.pop()
            if w.index in comp:
                continue
            comp.add(w.index)
            for e in w.link_edges:
                o = e.other_vert(w)
                if o.index not in comp:
                    stack.append(o)
        seen |= comp
        if len(comp) != 8:
            bm.free()
            return None
        pts = [bm.verts[i].co for i in comp]
        mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        # 8 정점이 정확히 bbox 의 꼭짓점이어야 축정렬 박스다
        for p in pts:
            for i in range(3):
                if abs(p[i] - mn[i]) > tol and abs(p[i] - mx[i]) > tol:
                    bm.free()
                    return None
        boxes.append(((mn + mx) / 2, mx - mn))
    bm.free()
    return boxes if boxes else None


# ------------------------------------------------------------ 그룹 배정

PART_COLLECTIONS = {"조정"}          # 네이티브 Part 로 바꿀 컬렉션
PART_NAME_PREFIX = ("담장",)

# 네이티브 Part 로 뺄 그룹. sites.py 로 위임한다 — 예전엔 ("CYD","WAL") 이
# 여기 박혀 있어서 덕수궁 마당(DYD)과 화성 지면(HGD)이 무시됐다.
# 실제 변환은 extract_boxes 가 순수 축정렬 박스일 때만 하므로, 그룹을 넣어도
# 자격이 안 되면 조용히 일반 메시로 나간다.
PART_GROUPS = set().union(*(s["part_groups"] for s in sites.SITES.values()))


def group_of(obj):
    """컬렉션 + 객체 이름 → 익스포트 그룹 코드.

    sites.py 로 위임한다. 예전에는 여기에 경복궁 전용 if 사슬이 박혀 있어서
    덕수궁과 화성이 통째로 MISC 로 떨어졌다. sites.SITES 는 궁궐이 늘어나도
    한 곳만 고치면 되고, import 시점에 그룹 코드 중복까지 막아 준다.
    경복궁에 대한 결과는 옛 if 사슬과 완전히 같다 — 규칙 순서가 그대로다.
    """
    coll = obj.users_collection[0].name if obj.users_collection else "?"
    return sites.group_of(coll, obj.name)


def material_key(obj):
    if obj.data.materials and obj.data.materials[0]:
        return obj.data.materials[0].name
    return ""


# ------------------------------------------------------------ 프리플라이트


def preflight():
    """내보내기 전 수정과 점검. 결과 dict 를 돌려준다."""
    rep = {"fixes": [], "asserts": [], "warnings": []}

    # P3 — 두께 0 인 박공에 Solidify (build_gable_roof 는 이걸 안 붙인다)
    n_gable = 0
    for o in bpy.data.objects:
        if o.type != 'MESH' or "_박공" not in o.name:
            continue
        if not any(m.type == 'SOLIDIFY' for m in o.modifiers):
            m = o.modifiers.new("두께", 'SOLIDIFY')
            m.thickness = 0.12
            m.offset = 0.0
            n_gable += 1
    rep["fixes"].append("박공 Solidify 추가: %d" % n_gable)

    # P6 — 고아 데이터블록 정리
    before = len(bpy.data.meshes)
    for _ in range(8):
        if bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True,
                                          do_recursive=True) == {'CANCELLED'}:
            break
    rep["fixes"].append("고아 메시 정리: %d → %d" % (before, len(bpy.data.meshes)))

    # P1/P7/P8/P9
    dg = bpy.context.evaluated_depsgraph_get()
    vis = [o for o in bpy.data.objects if o.type == 'MESH' and not o.hide_render]
    rep["asserts"].append("렌더 대상 메시 = %d" % len(vis))

    neg = [o.name for o in vis if o.matrix_world.determinant() < 0]
    rep["asserts"].append("음수 determinant(미러) = %d %s" % (len(neg), neg[:5]))

    scaled = []
    for o in vis:
        s = o.matrix_world.to_scale()
        if max(abs(s.x - 1), abs(s.y - 1), abs(s.z - 1)) > 1e-4:
            scaled.append((o.name, round(s.x, 5)))
    rep["asserts"].append("비단위 스케일 오브젝트 = %d (유물 서브트리여야 함)" % len(scaled))
    rep["scaled_sample"] = scaled[:8]

    thin = []
    for o in vis:
        if any(m.type == 'SOLIDIFY' for m in o.modifiers):
            base = len(o.data.polygons)
            ev = o.evaluated_get(dg)
            me = ev.to_mesh()
            got = len(me.polygons)
            ev.to_mesh_clear()
            if got < base * 1.9:
                thin.append(o.name)
    rep["asserts"].append("Solidify 미반영 의심 = %d %s" % (len(thin), thin[:5]))
    return rep


# --------------------------------------------------------------- 익스포트


def in_nc_collection(obj):
    """비상업(NC) 라이선스 에셋인가.

    **그룹 분류로는 걸러지지 않는다.** 레지스트리에 없는 컬렉션은 MISC 그룹을
    받는데, do_export 를 --groups 없이 부르면 MISC 도 그대로 나간다.
    즉 '등록만 안 하면 알아서 빠진다'는 것은 **틀렸다** — 여기서 명시적으로
    막아야 한다.

    NC 에셋(스파스카야·이반대제종탑·양파돔)은 렌더 컷 전용이다. 오버데어는
    UGC 게임 플랫폼이라 게시 자체가 비상업 조건에 걸리고, SA 는 파생물에
    전염된다. 수익화 여부와 무관하다.
    """
    return any(c.name in sites.NC_COLLECTIONS for c in obj.users_collection)


def collect_units():
    """모든 렌더 대상 메시를 익스포트 유닛/Part 로 변환한다."""
    dg = bpy.context.evaluated_depsgraph_get()
    units, parts, split_log = [], [], []
    skipped_nc = []

    for obj in sorted([o for o in bpy.data.objects
                       if o.type == 'MESH' and not o.hide_render],
                      key=lambda o: o.name):
        if in_nc_collection(obj):
            skipped_nc.append(obj.name)
            continue
        grp = group_of(obj)
        me = evaluated_world_mesh(obj, dg)
        src_tris = mesh_tris(me)

        # 조정·담장의 순수 박스는 네이티브 Part 로
        if grp in PART_GROUPS:
            boxes = extract_boxes(me)
            if boxes:
                for bi, (c, s) in enumerate(boxes):
                    px, py, pz = to_ovdr(c)
                    sx, sy, sz = to_ovdr_size(s)
                    parts.append({
                        "name": "%s_%02d" % (slug_for(obj.name), bi),
                        "source_object": obj.name,
                        "group": grp,
                        "material_key": material_key(obj),
                        "cframe_cm": {"X": round(px, 3), "Y": round(py, 3), "Z": round(pz, 3)},
                        "size_cm": {"X": round(sx, 3), "Y": round(sy, 3), "Z": round(sz, 3)},
                    })
                bpy.data.meshes.remove(me)
                continue

        src_polys = mesh_polys(me)
        pieces = split_mesh_lossless(me, CAP)
        if len(pieces) > 1:
            got_t = sum(mesh_tris(p) for p in pieces)
            got_p = sum(mesh_polys(p) for p in pieces)
            split_log.append({"object": obj.name, "tris": src_tris,
                              "polys": src_polys, "pieces": len(pieces),
                              "lossless": (got_t == src_tris and got_p == src_polys)})
            bpy.data.meshes.remove(me)

        for pi, pm in enumerate(pieces):
            mn, mx = mesh_bbox(pm)
            c = (mn + mx) / 2
            size = mx - mn
            px, py, pz = to_ovdr(c)
            sx, sy, sz = to_ovdr_size(size)
            base = slug_for(obj.name)
            slug = base if len(pieces) == 1 else "%s_p%02d" % (base, pi)
            units.append({
                "slug": slug,
                "source_object": obj.name,
                "group": grp,
                "material_key": material_key(obj),
                "tris": mesh_tris(pm),
                "polys": mesh_polys(pm),
                "budget": mesh_budget(pm),
                "verts": len(pm.vertices),
                "bbox_m": {"min": [round(v, 4) for v in mn],
                           "max": [round(v, 4) for v in mx],
                           "centre": [round(v, 4) for v in c]},
                "cframe_cm": {"X": round(px, 3), "Y": round(py, 3), "Z": round(pz, 3)},
                "size_cm": {"X": round(sx, 3), "Y": round(sy, 3), "Z": round(sz, 3)},
                "_mesh": pm,
            })
    return units, parts, split_log, skipped_nc


FBX_KWARGS = dict(
    use_selection=True, use_visible=False, use_active_collection=False,
    global_scale=1.0, apply_unit_scale=True,
    apply_scale_options='FBX_SCALE_NONE',
    use_space_transform=True, bake_space_transform=False,
    object_types={'MESH'},
    use_mesh_modifiers=True, use_mesh_modifiers_render=True,
    mesh_smooth_type='FACE', use_subsurf=False, use_mesh_edges=False,
    use_tspace=False, use_triangles=TRIANGULATE, use_custom_props=False,
    add_leaf_bones=False, bake_anim=False,
    # **텍스처를 버리지 않는다.** 화성처럼 색이 텍스처에 들어 있는 실측 모델은
    # 굽지 않으면 오버데어에서 회색 덩어리가 된다.
    # 경복궁·덕수궁은 단청 팔레트 단색이라 이미지 노드가 아예 없어서
    # 이 설정이 무해하다 — 구울 게 없으면 아무 일도 일어나지 않는다.
    # 용량 문제로 되돌리려면 --strip-textures.
    path_mode='COPY', embed_textures=True, batch_mode='OFF',
    use_metadata=True, axis_forward='-Z', axis_up='Y',
)


def export_pack(units, path):
    """유닛들을 임시 오브젝트로 만들어 하나의 FBX 로 내보낸다.

    메시는 이미 월드 좌표가 구워져 있고, 임포터가 어차피 재중심화하므로
    오브젝트 변환은 identity 로 둔다.
    """
    for o in list(bpy.context.scene.collection.objects):
        if o.name.startswith("_EXP_"):
            bpy.data.objects.remove(o, do_unlink=True)

    tmp = []
    for u in units:
        ob = bpy.data.objects.new(u["slug"], u["_mesh"])
        bpy.context.scene.collection.objects.link(ob)
        tmp.append(ob)

    bpy.ops.object.select_all(action='DESELECT')
    for ob in tmp:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = tmp[0] if tmp else None

    props = bpy.ops.export_scene.fbx.get_rna_type().properties.keys()
    kw = {k: v for k, v in FBX_KWARGS.items() if k in props}
    bpy.ops.export_scene.fbx(filepath=path, check_existing=False, **kw)

    for ob in tmp:
        bpy.data.objects.remove(ob, do_unlink=True)
    return os.path.getsize(path)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def palette_colors():
    """hanok.PALETTE 를 OVERDARE Color3 + Material 로 변환."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import hanok
        pal, names = hanok.PALETTE, hanok.MAT_NAMES
    except Exception:
        return {}
    mat_map = {
        'granite': 'Rock', 'granite_d': 'Rock', 'tile': 'Concrete',
        'wood_red': 'Wood', 'dc_green': 'Plastic', 'dc_red': 'Plastic',
        'dc_blue': 'Plastic', 'dc_white': 'Plastic', 'wood_dark': 'Wood',
        'paper': 'Plastic', 'floor': 'Concrete', 'gold': 'Metal',
        # 백골집 (덕수궁 석어당)
        'wood_bare': 'Wood', 'wood_aged': 'Wood', 'plaster': 'Concrete',
    }
    out = {}
    for key, (rgb, rough, metal) in pal.items():
        out[names[key]] = {
            "color3": srgb255(rgb),
            "material": mat_map.get(key, 'Basic'),
            "transparency": 0.15 if key == 'paper' else 0.0,
        }
    return out


def do_export(out_dir, only_groups=None, pack_cap=None):
    os.makedirs(out_dir, exist_ok=True)
    rep_pre = preflight()

    units, parts, split_log, skipped_nc = collect_units()
    if skipped_nc:
        print("NC 라이선스로 제외: %d 개 %s" % (len(skipped_nc), skipped_nc[:4]))
    if only_groups:
        keep = set(only_groups)
        units = [u for u in units if u["group"] in keep]
        parts = [p for p in parts if p["group"] in keep]

    # 슬러그 충돌 검사
    slugs = [u["slug"] for u in units]
    assert len(set(slugs)) == len(slugs), "슬러그 충돌: %s" % (
        [s for s in slugs if slugs.count(s) > 1][:5])

    # 상한은 **파일당**이다. 여유를 두고 채운다.
    if pack_cap is None:
        pack_cap = int(CAP * 0.96)
    packs, by_group = [], {}
    for u in units:
        by_group.setdefault(u["group"], []).append(u)
    for grp in sorted(by_group):
        cur, acc, idx = [], 0, 1
        for u in by_group[grp]:
            if cur and acc + u["budget"] > pack_cap:
                packs.append(("%s_%02d" % (grp, idx), cur))
                cur, acc, idx = [], 0, idx + 1
            cur.append(u)
            acc += u["budget"]
        if cur:
            packs.append(("%s_%02d" % (grp, idx), cur))

    files = []
    for name, us in packs:
        path = os.path.join(out_dir, name + ".fbx")
        size = export_pack(us, path)
        for u in us:
            u["file"] = name + ".fbx"
            # 메시가 하나뿐인 FBX 는 에셋 이름에 메시명 접미사가 붙지 않는다
            u["expected_asset_name"] = name if len(us) == 1 else "%s_%s" % (name, u["slug"])
        files.append({"file": name + ".fbx", "bytes": size,
                      "sha256": sha256_of(path),
                      "meshes": len(us),
                      "tris": sum(u["tris"] for u in us),
                      "polys": sum(u["polys"] for u in us),
                      "budget": sum(u["budget"] for u in us),
                      "mesh_slugs": [u["slug"] for u in us]})
        print("PACK %-14s %3d meshes  polys=%6d tris=%7d  budget=%6d  %9d bytes" %
              (name, len(us), sum(u["polys"] for u in us),
               sum(u["tris"] for u in us), sum(u["budget"] for u in us), size))

    for u in units:
        u.pop("_mesh", None)

    manifest = {
        "schema": "overdare-export/2",
        "blend_file": bpy.data.filepath,
        "calibration": {
            "verified": "2026-08-10 CHECKPOINT A (측정값, 추정 아님)",
            "axis_map": "Blender (x,y,z) -> OVERDARE (X=x*100, Y=z*100+FLOOR_Y, Z=-y*100)",
            "unit_cm_per_blender_unit": CM,
            "floor_y_cm": FLOOR_Y,
            "pivot_mode": "bbox_recentred",
            "orientation": "항상 0 — 회전은 메시에 구워진다",
            "evidence": "CAL 메시 5개를 같은 CFrame 에 놨더니 한 점에 겹쳤다",
        },
        "cap": CAP,
        "cap_scope": "per_file (2026-08-10 실측: 51,816 삼각형 단일 파일 거부됨)",
        "triangulated": TRIANGULATE,
        "preflight": rep_pre,
        "splits": split_log,
        # 라이선스 감사용. 비어 있지 않다면 그 오브젝트들은 렌더 전용이다.
        "skipped_nc": skipped_nc,
        "palette": palette_colors(),
        "files": files,
        "meshes": units,
        "parts": parts,
        "totals": {
            "meshes": len(units), "parts": len(parts),
            "tris": sum(u["tris"] for u in units),
            "polys": sum(u["polys"] for u in units),
            "files": len(files),
            "bytes": sum(f["bytes"] for f in files),
        },
    }
    mp = os.path.join(out_dir, "manifest.json")
    with open(mp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print("MANIFEST %s  (%d bytes)" % (mp, os.path.getsize(mp)))
    return manifest


# ------------------------------------------------------------------ main


def main():
    args = argv_after_dashdash()
    out = get_arg(args, "--out", r"C:\Users\HSP\Desktop\blender\ovdr_export")

    if has_flag(args, "--calibrate"):
        print("캘리브레이션은 2026-08-10 에 완료됐다. 결과는 상단 주석과 "
              "manifest.calibration 에 있다. 다시 필요하면 git 이력에서 "
              "build_calibration() 을 되살릴 것.")
        return

    if has_flag(args, "--export"):
        global TRIANGULATE
        if has_flag(args, "--triangulate"):
            TRIANGULATE = True
            FBX_KWARGS["use_triangles"] = True
        if has_flag(args, "--strip-textures"):
            # 탈출구. 임포터가 FBX 임베디드 텍스처를 거부하거나 파일이 너무
            # 클 때만 쓴다. 스캔 사이트에서는 색을 통째로 버리는 것이다.
            FBX_KWARGS["path_mode"] = 'STRIP'
            FBX_KWARGS["embed_textures"] = False
        groups = get_arg(args, "--groups")
        only = groups.split(",") if groups else None
        m = do_export(out, only_groups=only)
        print("MODE triangulate=%s  cap=%d/파일" % (TRIANGULATE, CAP))
        t = m["totals"]
        print("PRE: " + " | ".join(m["preflight"]["fixes"]))
        for a in m["preflight"]["asserts"]:
            print("PRE: " + a)
        bad = [s for s in m["splits"] if not s["lossless"]]
        print("SPLIT %d 건, 무손실 아님 %d 건 %s" %
              (len(m["splits"]), len(bad), [s["object"] for s in bad[:3]]))
        print("TOTAL meshes=%d parts=%d polys=%d tris=%d files=%d bytes=%d" %
              (t["meshes"], t["parts"], t["polys"], t["tris"], t["files"], t["bytes"]))
        print("EXPORT DONE")
        return

    print("할 일: --calibrate | --export [--groups GJJ,SJJ] [--strip-textures]")


if __name__ == "__main__":
    main()
