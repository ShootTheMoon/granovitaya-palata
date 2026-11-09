# -*- coding: utf-8 -*-
"""절차적 한옥(궁궐 전각) 생성기.

경복궁 근정전/사정전을 세우기 위한 부재별 빌더.
다포계 팔작지붕을 기준으로 하며, 처마의 앙곡(corner lift)과
안허리곡(corner extension)을 변형 함수로 적용한다.
"""

import bpy
import bmesh
import math
from mathutils import Vector

# ---------------------------------------------------------------- 기본 유틸


# AgX 톤매핑을 쓴다. (Blender 의 view_transform 은 OCIO 가 채우는 동적 enum
# 이라 enum_items 로 조회하면 NONE 하나만 보이지만, 실제로는 AgX 가 있다.)
# 하이라이트가 살아 있으므로 알베도는 실제 값에 가깝게 잡는다.
PALETTE = {
    'granite':   ((0.42, 0.41, 0.38), 0.88, 0.0),
    'granite_d': ((0.29, 0.28, 0.26), 0.92, 0.0),
    'tile':      ((0.11, 0.12, 0.14), 0.58, 0.0),
    'wood_red':  ((0.36, 0.09, 0.06), 0.58, 0.0),
    'dc_green':  ((0.04, 0.21, 0.15), 0.52, 0.0),
    # 뇌록(磊碌) — 모루단청의 **바탕색**. 채도 높은 녹청은 부재 *끝*에만 쓰고
    # 긴 민면은 이 차분한 회녹색이다. 지금까지 부재 전체를 dc_green 통색으로
    # 칠해 온 것이 "테마파크처럼 보인다"의 가장 큰 원인이다.
    'noerok':    ((0.155, 0.190, 0.150), 0.72, 0.0),
    'moru_red':  ((0.40, 0.10, 0.07), 0.56, 0.0),
    'dc_red':    ((0.44, 0.08, 0.05), 0.52, 0.0),
    'dc_blue':   ((0.06, 0.14, 0.29), 0.52, 0.0),
    'dc_white':  ((0.66, 0.63, 0.57), 0.60, 0.0),
    'wood_dark': ((0.17, 0.09, 0.05), 0.68, 0.0),
    'paper':     ((0.70, 0.63, 0.47), 0.78, 0.0),
    'floor':     ((0.17, 0.16, 0.15), 0.88, 0.0),
    'gold':      ((0.62, 0.47, 0.15), 0.32, 0.9),
    # 백골집(단청 없는 맨 나무) — 덕수궁 석어당
    'wood_bare': ((0.30, 0.22, 0.14), 0.80, 0.0),
    'wood_aged': ((0.22, 0.16, 0.11), 0.84, 0.0),
    'plaster':   ((0.62, 0.60, 0.54), 0.86, 0.0),
    # --- 화성 주변 현대 도시(hwaseong/city.py). 궁궐 팔레트와 섞이지 않게
    #     키를 따로 둔다. 텍스처 없이 Color3 로만 칠해지므로 명도 차로 구분한다.
    'concrete':   ((0.50, 0.49, 0.46), 0.82, 0.0),
    'concrete_d': ((0.34, 0.33, 0.31), 0.86, 0.0),
    'brick_city': ((0.33, 0.22, 0.17), 0.84, 0.0),
    'panel_warm': ((0.55, 0.47, 0.38), 0.80, 0.0),
    'glass':      ((0.13, 0.19, 0.25), 0.18, 0.0),
    'asphalt':    ((0.075, 0.075, 0.085), 0.92, 0.0),
    # 도로망이 읽히려면 **지반과 명도 차가 있어야 한다.** 처음엔 지면 슬래브
    # (전돌 0.17)와 보도(0.44)가 둘 다 중간 회색이라 아무것도 안 보였다.
    # 도시 지반을 concrete_d(0.34)로 따로 깔고, 차도는 그보다 훨씬 어둡게,
    # 보도는 훨씬 밝게 벌려 놓는다.
    'sidewalk':   ((0.56, 0.55, 0.52), 0.90, 0.0),
    # --- 한옥 마을이 된 뒤의 흙길. 아스팔트·보도블럭을 대체한다.
    #     블렌더에서는 terrain.py 가 Poly Haven CC0 텍스처로 덮어쓰지만,
    #     오버데어는 Color3 만 받으므로 이 색이 그대로 게임에 나간다.
    #     잔디 지면(0.24)보다 밝아야 길이 읽힌다.
    'dirt_road':  ((0.46, 0.38, 0.29), 0.94, 0.0),
    'dirt_path':  ((0.52, 0.45, 0.36), 0.93, 0.0),
    'dirt_verge': ((0.31, 0.32, 0.20), 0.95, 0.0),   # 갓길: 흙과 잔디 사이
    'grass':      ((0.20, 0.26, 0.13), 0.95, 0.0),
    # --- 모스크바 크렘린(kremlin/). 궁궐·도시 팔레트와 키를 따로 둔다.
    #     성벽은 1485~95년 붉은 벽돌이지만 지금 보이는 붉은색은 소비에트기부터
    #     칠해 온 도료다. 벽돌 소재색(brick_city 0.33/0.22/0.17)보다 채도가
    #     훨씬 높아야 사진과 맞는다.
    'brick_red':   ((0.34, 0.115, 0.085), 0.86, 0.0),
    'brick_red_d': ((0.24, 0.078, 0.058), 0.89, 0.0),   # 켜쌓기 들이밈 줄눈
    # 금박 돔. sRGB (1.000, 0.766, 0.336) 이 물리 기반 금 반사율인데 PALETTE 는
    # 선형값을 그대로 Base Color 에 넣으므로 환산해서 적는다.
    #   0.766 → 0.548,  0.336 → 0.092
    # 실제 질감은 HDRI 반사가 만든다. Roughness 를 0 으로 두면 거울이 되어
    # 흐린 하늘 아래서 오히려 죽는다.
    'gold_dome':   ((1.000, 0.548, 0.092), 0.22, 1.0),
    # 구리 녹청 지붕 — 대크렘린궁·상원궁 돔
    'green_roof':  ((0.075, 0.190, 0.155), 0.60, 0.0),
    # 루비 유리 별. 내부 백열등이 들어 있어 밤에는 발광하지만, 베이스 컬러만
    # 여기 둔다 — 이미션은 별도 노드로 붙인다(익스포터가 Color3 만 읽으므로).
    'star_ruby':   ((0.42, 0.022, 0.030), 0.16, 0.0),
    # 백석(белый камень) — 3대 성당·나리치닉·가리비 자코마라
    'whitewash':   ((0.72, 0.69, 0.63), 0.85, 0.0),
    # 성 바실리 대성당의 다색 돔. 크렘린 3대 성당이 전부 금박인 것과 달리
    # 여기만 나선·마름모 무늬의 원색이고, **그게 이 건물의 정체성**이라
    # 금박 하나로 뭉개면 알아볼 수가 없다. 1680년대 채색이 현재 모습이다.
    'dome_red':    ((0.40, 0.075, 0.055), 0.42, 0.0),
    'dome_green':  ((0.055, 0.26, 0.13), 0.42, 0.0),
    'dome_blue':   ((0.045, 0.13, 0.36), 0.42, 0.0),
    'dome_ochre':  ((0.52, 0.32, 0.055), 0.44, 0.0),
    # 화강암 — 레닌묘. 붉은 카렐리야 규암 + 라브라도라이트
    'granite_red': ((0.22, 0.085, 0.075), 0.55, 0.0),
    # --- 파세트궁 실내(kremlin/interior.py).
    #     이 방은 바닥부터 볼트까지 **전면 프레스코**라, 흰 회벽으로 두면
    #     블록아웃으로 보인다. 색은 ref/05_대크렘린궁/_indoor/17.jpg 에서
    #     읽었다 — 황토 바탕에 적갈색 테두리 띠다(사진 자체는 파세트궁 실내).
    #     sRGB → 선형 환산해서 적는다. 황토 (0.80,0.70,0.50) → 아래 값.
    'fresco_gold':  ((0.603, 0.448, 0.212), 0.80, 0.0),
    'fresco_band':  ((0.168, 0.033, 0.021), 0.72, 0.0),   # 적갈색 테두리·다도
    # подклет 은 칠하지 않은 석조다. 위층과 대비가 나야 두 층이 다른 방으로
    # 읽힌다 — 둘 다 밝은 회벽이면 계단만 있는 한 공간처럼 보인다.
    'undercroft':   ((0.235, 0.222, 0.198), 0.90, 0.0),
    'floor_stone':  ((0.145, 0.138, 0.128), 0.86, 0.0),   # 대홀 — 다듬은 석판
    'floor_rough':  ((0.115, 0.110, 0.102), 0.92, 0.0),   # 아랫층 — 거친 깔돌
    'iron_dark':    ((0.045, 0.040, 0.036), 0.55, 0.35),  # 창살
}

MAT_NAMES = {
    'granite': "MAT_화강암", 'granite_d': "MAT_화강암_어둡",
    'tile': "MAT_기와", 'wood_red': "MAT_기둥_주칠",
    'dc_green': "MAT_단청_녹", 'dc_red': "MAT_단청_적",
    'noerok': "MAT_뇌록", 'moru_red': "MAT_모루_적",
    'dc_blue': "MAT_단청_청", 'dc_white': "MAT_단청_백",
    'wood_dark': "MAT_목재_암", 'paper': "MAT_창호지",
    'floor': "MAT_전돌", 'gold': "MAT_금",
    'wood_bare': "MAT_백골", 'wood_aged': "MAT_백골_고재",
    'plaster': "MAT_회벽",
    'concrete': "MAT_콘크리트", 'concrete_d': "MAT_콘크리트_암",
    'brick_city': "MAT_붉은벽돌", 'panel_warm': "MAT_외장패널",
    'glass': "MAT_유리", 'asphalt': "MAT_아스팔트", 'sidewalk': "MAT_보도",
    'dirt_road': "MAT_흙길", 'dirt_path': "MAT_샛길", 'grass': "MAT_잔디",
    'dirt_verge': "MAT_갓길",
    'brick_red': "MAT_크렘린_벽돌", 'brick_red_d': "MAT_크렘린_벽돌_암",
    'gold_dome': "MAT_금박돔", 'green_roof': "MAT_녹청지붕",
    'star_ruby': "MAT_루비별", 'whitewash': "MAT_백석",
    'dome_red': "MAT_돔_적", 'dome_green': "MAT_돔_녹",
    'dome_blue': "MAT_돔_청", 'dome_ochre': "MAT_돔_황",
    'granite_red': "MAT_적화강암",
    'fresco_gold': "MAT_프레스코_황", 'fresco_band': "MAT_프레스코_적",
    'undercroft': "MAT_하층석조", 'floor_stone': "MAT_바닥석",
    'floor_rough': "MAT_바닥거친",
    'iron_dark': "MAT_철물",
}

# ---- 부재 역할 → 재질 키 --------------------------------------------------
#
# 빌더들이 재질을 문자열 리터럴로 박아 두면 백골집(단청 없는 건물)을 만들 수
# 없다. 역할 딕셔너리를 통째로 갈아끼우는 방식으로 바꾼다.
# 모든 빌더는 후행 인자 pal=None 을 받고 pal = pal or DANCHEONG 로 시작하므로
# 기존 호출부는 전혀 영향을 받지 않는다.

DANCHEONG = dict(
    # beam·arm·rafter 를 dc_green → noerok 으로 바꿨다. 모루단청은 문양이
    # 부재 **끝**에 몰리고 사이는 뇌록의 긴 민면이다. 진한 청록 통색은
    # 실제 단청과 다르고, 축소해서 봐도 살아남는 종류의 오류다.
    stone='granite', col='wood_red', beam='noerok', arm='noerok',
    block='dc_red', paper='paper', lattice='dc_red', frame='noerok',
    tile='tile', gable='dc_white', rafter='noerok', floor='wood_dark',
)

# 석어당 — 도료를 칠하지 않은 맨 나무. 취두·용두·잡상도 없다.
BAEKGOL = dict(
    DANCHEONG,
    col='wood_bare', beam='wood_bare', arm='wood_bare', block='wood_bare',
    lattice='wood_aged', frame='wood_bare', gable='plaster',
    rafter='wood_bare',
)

# 모스크바 크렘린 — 목조 부재가 없으므로 역할 이름만 빌려 쓴다.
# hanok.build_columns/build_platform/build_balustrade 를 성당 아케이드와
# 기단에 그대로 재사용하기 위한 매핑이다. tile 은 지붕이 아니라 **돔**이다.
KREMLIN = dict(
    DANCHEONG,
    stone='brick_red', col='whitewash', beam='whitewash', arm='whitewash',
    block='whitewash', frame='whitewash', lattice='gold_dome',
    tile='gold_dome', gable='whitewash', rafter='whitewash',
    floor='granite_d', paper='whitewash',
)


def setup_materials():
    """팔레트를 만들거나 이미 있으면 값을 갱신한다."""
    for key, (rgb, rough, metal) in PALETTE.items():
        name = MAT_NAMES[key]
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes.get("Principled BSDF")
        b.inputs["Base Color"].default_value = (*rgb, 1.0)
        b.inputs["Roughness"].default_value = rough
        b.inputs["Metallic"].default_value = metal
    return len(PALETTE)


def get_mat(key):
    """단청 팔레트에서 머티리얼을 가져온다."""
    return bpy.data.materials.get(MAT_NAMES[key])


def new_collection(name, parent=None):
    """주의: 같은 이름이면 기존 컬렉션을 그대로 돌려준다(조용한 병합).

    궁궐이 둘 이상이면 컬렉션 이름을 반드시 사이트별로 구분해야 한다.
    sites.py 의 레지스트리가 그 규약을 강제한다.
    """
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(coll)
    return coll


def place_objects(objs, origin=(0.0, 0.0, 0.0), rot_z=0.0, matrix=None):
    """이미 놓인 트랜스폼 **위에** 사이트 배치를 덧씌운다 (합성, 대입 아님).

    지금까지 배치 관용구가 두 가지로 갈려 있었고 서로 합성이 안 됐다:
      build.py   : ob.location.y += ...   (상대 가산)
      enclosure  : ob.location = loc      (절대 대입)
    행렬 합성으로 통일하면 둘 다, 그리고 회전까지 겹쳐 쓸 수 있다.

    규칙: 이 함수를 돌린 컬렉션에는 이후 location/rotation_euler 를 대입하지
    말 것. 대입은 여기서 합성한 결과를 지운다.
    """
    from mathutils import Matrix
    M = matrix or (Matrix.Translation(origin) @ Matrix.Rotation(rot_z, 4, 'Z'))
    for ob in objs:
        ob.matrix_world = M @ ob.matrix_world
    return objs


def mesh_object(name, verts, faces, mat_key, coll):
    """정점/면 리스트로 오브젝트를 만든다."""
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate()
    me.update()
    ob = bpy.data.objects.new(name, me)
    ob.data.materials.append(get_mat(mat_key))
    coll.objects.link(ob)
    return ob


def bm_to_object(bm, name, mat_key, coll):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.validate()
    ob = bpy.data.objects.new(name, me)
    ob.data.materials.append(get_mat(mat_key))
    coll.objects.link(ob)
    return ob


def box_verts_faces(cx, cy, cz, sx, sy, sz):
    """중심과 크기로 육면체의 정점/면을 만든다."""
    hx, hy, hz = sx / 2.0, sy / 2.0, sz / 2.0
    v = [
        (cx - hx, cy - hy, cz - hz), (cx + hx, cy - hy, cz - hz),
        (cx + hx, cy + hy, cz - hz), (cx - hx, cy + hy, cz - hz),
        (cx - hx, cy - hy, cz + hz), (cx + hx, cy - hy, cz + hz),
        (cx + hx, cy + hy, cz + hz), (cx - hx, cy + hy, cz + hz),
    ]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
         (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return v, f


def bm_box(bm, cx, cy, cz, sx, sy, sz):
    """bmesh 에 육면체를 누적한다."""
    v, f = box_verts_faces(cx, cy, cz, sx, sy, sz)
    bv = [bm.verts.new(p) for p in v]
    for face in f:
        bm.faces.new([bv[i] for i in face])


def bm_taper_box(bm, cz, sz, x0, y0, x1, y1):
    """아래(x0,y0) → 위(x1,y1) 로 좁아지는 사다리꼴 기둥(민흘림 기단용)."""
    zb, zt = cz - sz / 2.0, cz + sz / 2.0
    b = [(-x0, -y0, zb), (x0, -y0, zb), (x0, y0, zb), (-x0, y0, zb)]
    t = [(-x1, -y1, zt), (x1, -y1, zt), (x1, y1, zt), (-x1, y1, zt)]
    bv = [bm.verts.new(p) for p in b + t]
    for face in [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                 (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]:
        bm.faces.new([bv[i] for i in face])


def bm_cylinder(bm, cx, cy, z0, z1, r0, r1, seg=16):
    """원기둥/원뿔대. 배흘림 기둥은 이걸 여러 마디로 쌓아 표현한다."""
    ring0, ring1 = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        ring0.append(bm.verts.new((cx + r0 * math.cos(a), cy + r0 * math.sin(a), z0)))
        ring1.append(bm.verts.new((cx + r1 * math.cos(a), cy + r1 * math.sin(a), z1)))
    for i in range(seg):
        j = (i + 1) % seg
        bm.faces.new([ring0[i], ring0[j], ring1[j], ring1[i]])
    bm.faces.new(list(reversed(ring0)))
    bm.faces.new(ring1)


def bm_entasis_column(bm, cx, cy, z0, height, r_base, seg=16, steps=8):
    """배흘림기둥 — 아래 1/3 지점이 가장 굵은 곡선 프로파일."""
    prev = None
    for s in range(steps + 1):
        t = s / steps
        # 0 에서 1 로 가며 0.33 부근이 최대가 되는 완만한 배흘림
        bulge = 1.0 + 0.055 * math.sin(math.pi * min(1.0, t * 1.15) ** 0.85)
        taper = 1.0 - 0.16 * t
        r = r_base * bulge * taper
        z = z0 + height * t
        ring = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            ring.append(bm.verts.new((cx + r * math.cos(a), cy + r * math.sin(a), z)))
        if prev is None:
            bm.faces.new(list(reversed(ring)))
        else:
            for i in range(seg):
                j = (i + 1) % seg
                bm.faces.new([prev[i], prev[j], ring[j], ring[i]])
        prev = ring
    bm.faces.new(prev)


def bm_square_column(bm, cx, cy, z0, height, half, taper=0.14):
    """민흘림 각기둥 — 위로 갈수록 살짝 좁아지는 사각 기둥.

    덕수궁 즉조당처럼 네모기둥을 쓰는 건물용. 원형 배흘림기둥과 달리
    배부름 없이 곧게 좁아진다.
    """
    b, t = half, half * (1.0 - taper)
    zb, zt = z0, z0 + height
    v = [(cx - b, cy - b, zb), (cx + b, cy - b, zb),
         (cx + b, cy + b, zb), (cx - b, cy + b, zb),
         (cx - t, cy - t, zt), (cx + t, cy - t, zt),
         (cx + t, cy + t, zt), (cx - t, cy + t, zt)]
    bv = [bm.verts.new(p) for p in v]
    for f in [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
              (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]:
        bm.faces.new([bv[i] for i in f])


def grid_positions(bays):
    """칸 폭 리스트 → 기둥 중심 좌표(중앙 기준)."""
    total = sum(bays)
    pos, x = [-total / 2.0], -total / 2.0
    for b in bays:
        x += b
        pos.append(x)
    return pos, total


# ------------------------------------------------------------ 기단 / 월대


def build_platform(name, coll, cx, cy, z0, height, sx, sy,
                   batter=0.25, mat='granite'):
    """장대석 기단. 위로 갈수록 살짝 좁아진다.

    메시는 원점 기준으로 만들고 위치는 오브젝트 트랜스폼으로만 준다.
    (예전엔 갑석만 메시에 (cx,cy) 를 굽고 오브젝트에도 같은 값을 넣어
     이중 오프셋이었다. 모든 호출이 cx=cy=0 이라 드러나지 않았을 뿐이다.)
    """
    bm = bmesh.new()
    bm_taper_box(bm, z0 + height / 2.0, height,
                 sx / 2.0, sy / 2.0,
                 sx / 2.0 - batter, sy / 2.0 - batter)
    # 갑석(맨 위 마감돌) — 살짝 내밀어 그림자선을 만든다
    bm_box(bm, 0, 0, z0 + height + 0.09, sx - 2 * batter + 0.30,
           sy - 2 * batter + 0.30, 0.18)
    ob = bm_to_object(bm, name, mat, coll)
    ob.location = (cx, cy, 0)
    return ob


def build_stairs(name, coll, cx, y_front, z0, height, width,
                 run=0.42, mat='granite', sgn=-1.0):
    """계단. sgn=-1 이면 남쪽(-y)으로, +1 이면 북쪽(+y)으로 내려간다."""
    n = max(2, int(round(height / 0.30)))
    rise = height / n
    bm = bmesh.new()
    for i in range(n):
        depth = run * (n - i)
        bm_box(bm, cx, y_front + sgn * depth / 2.0, z0 + rise * (i + 0.5),
               width, depth, rise)
    return bm_to_object(bm, name, mat, coll)


def build_dapdo(name, coll, cx, y_front, z0, height, width, mat='granite_d'):
    """답도 — 계단 가운데 봉황을 새긴 경사 석판."""
    run = 0.42 * max(2, int(round(height / 0.30)))
    bm = bmesh.new()
    hw = width / 2.0
    y0, y1 = y_front - run, y_front
    v = [(cx - hw, y0, z0 + height), (cx + hw, y0, z0 + height),
         (cx + hw, y1, z0), (cx - hw, y1, z0),
         (cx - hw, y0, z0 + height - 0.14), (cx + hw, y0, z0 + height - 0.14),
         (cx + hw, y1, z0 - 0.14), (cx - hw, y1, z0 - 0.14)]
    bv = [bm.verts.new(p) for p in v]
    for f in [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1),
              (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]:
        bm.faces.new([bv[i] for i in f])
    return bm_to_object(bm, name, mat, coll)


def build_balustrade(name, coll, z0, sx, sy, height=1.05, mat='granite'):
    """월대 돌난간 — 엄지기둥(동자석) + 돌란대."""
    bm = bmesh.new()
    hx, hy = sx / 2.0, sy / 2.0
    spacing = 2.1

    def run_posts(axis, fixed, lo, hi):
        n = max(2, int(round((hi - lo) / spacing)))
        for i in range(n + 1):
            t = lo + (hi - lo) * i / n
            px, py = (t, fixed) if axis == 'x' else (fixed, t)
            bm_box(bm, px, py, z0 + height * 0.55, 0.30, 0.30, height * 1.1)
            bm_box(bm, px, py, z0 + height * 1.16, 0.40, 0.40, 0.14)

    for fy in (-hy, hy):
        run_posts('x', fy, -hx, hx)
        bm_box(bm, 0, fy, z0 + height * 0.86, sx, 0.20, 0.17)
        bm_box(bm, 0, fy, z0 + height * 0.42, sx, 0.15, 0.13)
    for fx in (-hx, hx):
        run_posts('y', fx, -hy, hy)
        bm_box(bm, fx, 0, z0 + height * 0.86, 0.20, sy, 0.17)
        bm_box(bm, fx, 0, z0 + height * 0.42, 0.15, sy, 0.13)
    return bm_to_object(bm, name, mat, coll)


# ------------------------------------------------------- 기둥 / 창방 / 공포


def build_columns(name, coll, xs, ys, z0, height, radius,
                  perimeter_only=False, skip=None, shape='round', pal=None):
    """초석 + 기둥. skip 은 (xi, yi) 인덱스 집합.

    shape='round'  원형 초석 + 배흘림기둥 (경복궁, 덕수궁 중화전)
    shape='square' 네모 초석 + 민흘림 각기둥 (덕수궁 즉조당)
    """
    pal = pal or DANCHEONG
    skip = skip or set()
    bm_stone = bmesh.new()
    bm_col = bmesh.new()
    placed = []
    for xi, x in enumerate(xs):
        for yi, y in enumerate(ys):
            if (xi, yi) in skip:
                continue
            edge = xi in (0, len(xs) - 1) or yi in (0, len(ys) - 1)
            if perimeter_only and not edge:
                continue
            if shape == 'square':
                bm_box(bm_stone, x, y, z0 + 0.13, radius * 3.1, radius * 3.1, 0.37)
                bm_square_column(bm_col, x, y, z0 + 0.32, height, radius)
            else:
                bm_cylinder(bm_stone, x, y, z0 - 0.05, z0 + 0.32,
                            radius * 1.65, radius * 1.45, 20)
                bm_entasis_column(bm_col, x, y, z0 + 0.32, height, radius)
            placed.append((x, y))
    stones = bm_to_object(bm_stone, name + "_초석", pal['stone'], coll)
    cols = bm_to_object(bm_col, name + "_기둥", pal['col'], coll)
    return stones, cols, placed


def build_beams(name, coll, xs, ys, z_top, depth=0.52, thick=0.34,
                pyeongbang=True, pal=None):
    """창방 + 평방 — 기둥 머리를 잇는 수평 부재.

    평방은 다포계에만 있다. 익공계(덕수궁 즉조당·준명당·석어당 1층)는
    pyeongbang=False 로 창방만 건다.
    """
    pal = pal or DANCHEONG
    bm = bmesh.new()
    x0, x1, y0, y1 = xs[0], xs[-1], ys[0], ys[-1]
    sx, sy = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    zc = z_top - depth / 2.0
    for fy in (y0, y1):                       # 창방 (전후)
        bm_box(bm, cx, fy, zc, sx + thick, thick, depth)
    for fx in (x0, x1):                       # 창방 (좌우)
        bm_box(bm, fx, cy, zc, thick, sy + thick, depth)
    if pyeongbang:                             # 평방 — 다포계에만 있다
        zp = z_top + 0.13
        for fy in (y0, y1):
            bm_box(bm, cx, fy, zp, sx + 0.72, 0.60, 0.26)
        for fx in (x0, x1):
            bm_box(bm, fx, cy, zp, 0.60, sy + 0.72, 0.26)
    return bm_to_object(bm, name, pal['beam'], coll)


def build_brackets(name, coll, xs, ys, z_base, tiers=4, spacing=1.9, pal=None):
    """다포식 공포 — 주상포 + 주간포를 첨차/살미 십자 적층으로 표현.

    한계: 내부 line() 이 spacing 으로 균등 간격을 재계산하므로 기둥 위치와
    무관하게 놓인다. 다포계는 주간포가 있어 문제없지만, 익공계처럼 기둥머리
    에만 놓아야 하는 경우엔 쓸 수 없다 → build_ikgong 을 쓸 것.
    또 측면이 1칸뿐인 구조에서는 lo>hi 가 되어 두 세트가 가운데로 뭉친다.
    """
    pal = pal or DANCHEONG
    bm_green = bmesh.new()
    bm_red = bmesh.new()

    def one_set(px, py):
        for t in range(tiers):
            z = z_base + 0.30 + t * 0.34
            reach = 0.95 + t * 0.30          # 위로 갈수록 밖으로 뻗는 출목
            bm_box(bm_green, px, py, z, reach * 2, 0.26, 0.20)   # 첨차
            bm_box(bm_green, px, py, z, 0.26, reach * 2, 0.20)   # 살미
            bm_box(bm_red, px, py, z + 0.17, 0.42, 0.42, 0.15)   # 소로/주두
        bm_red_z = z_base + 0.30 + tiers * 0.34
        bm_box(bm_red, px, py, bm_red_z, 0.58, 0.58, 0.22)

    def line(axis, fixed, lo, hi):
        n = max(1, int(round((hi - lo) / spacing)))
        for i in range(n + 1):
            t = lo + (hi - lo) * i / n
            one_set(t, fixed) if axis == 'x' else one_set(fixed, t)

    for fy in (ys[0], ys[-1]):
        line('x', fy, xs[0], xs[-1])
    for fx in (xs[0], xs[-1]):
        line('y', fx, ys[0] + spacing, ys[-1] - spacing)

    g = bm_to_object(bm_green, name + "_공포", pal['arm'], coll)
    r = bm_to_object(bm_red, name + "_소로", pal['block'], coll)
    return g, r


def build_ikgong(name, coll, xs, ys, z_base, tiers=1, reach=0.95, rise=0.30,
                 wing=0.34, thick=0.22, boaji=True, pal=None):
    """익공(翼工)계 공포 — 기둥 머리에만 놓인다.

    다포계와 결정적으로 다른 점:
      · 주간포가 **없다.** 기둥과 기둥 사이는 비어 있다.
      · 쇠서(牛舌)가 **바깥으로만** 뻗는다. 다포의 대칭 십자와 다르다.
    그래서 build_brackets 를 재활용할 수 없다 — 그쪽은 spacing 으로 균등
    간격을 재계산하느라 기둥 위치를 아예 보지 않는다.

    tiers=1 초익공, 2 이익공.
    반환값은 build_brackets 와 같은 (팔, 소로) 2-튜플이라 그대로 바꿔 낀다.

    대상: 덕수궁 석어당 1층, 준명당, 즉조당, 복도각.
    """
    pal = pal or DANCHEONG
    bm_arm = bmesh.new()
    bm_blk = bmesh.new()

    x0, x1, y0, y1 = xs[0], xs[-1], ys[0], ys[-1]

    def one_set(px, py):
        # 주두 — 기둥 머리에 얹히는 네모 받침
        bm_box(bm_blk, px, py, z_base + 0.11, 0.62, 0.62, 0.22)
        # 바깥 방향 결정: 테두리에 있으면 그 방향으로만 쇠서를 낸다
        dirs = []
        if abs(px - x0) < 1e-6:
            dirs.append((-1.0, 0.0))
        if abs(px - x1) < 1e-6:
            dirs.append((1.0, 0.0))
        if abs(py - y0) < 1e-6:
            dirs.append((0.0, -1.0))
        if abs(py - y1) < 1e-6:
            dirs.append((0.0, 1.0))
        for t in range(tiers):
            z = z_base + 0.22 + t * rise
            for (dx, dy) in dirs:
                # 쇠서 — 기둥 밖으로 뻗어 처마를 받는다
                cx = px + dx * reach / 2.0
                cy = py + dy * reach / 2.0
                sx = reach if dx else wing
                sy = reach if dy else wing
                bm_box(bm_arm, cx, cy, z, sx, sy, thick)
            # 소로 — 쇠서 위에 얹히는 작은 받침
            bm_box(bm_blk, px, py, z + thick * 0.9, 0.40, 0.40, 0.16)
        if boaji:
            # 보아지 — 안쪽에서 보를 받치는 짧은 부재
            bm_box(bm_arm, px, py, z_base + 0.22 + tiers * rise * 0.5,
                   0.30, 0.30, tiers * rise)

    for xi, x in enumerate(xs):
        for yi, y in enumerate(ys):
            if xi in (0, len(xs) - 1) or yi in (0, len(ys) - 1):
                one_set(x, y)

    return (bm_to_object(bm_arm, name + "_익공", pal['arm'], coll),
            bm_to_object(bm_blk, name + "_소로", pal['block'], coll))


def build_gyeja_railing(name, coll, x0, x1, y, z0, height=0.75,
                        post_gap=0.9, pal=None, axis='x'):
    """계자난간 — 궁판 + 돌란대 + 하엽동자.

    월대용 석난간(build_balustrade)과는 부재 어휘가 전혀 다르다. 이쪽은
    목조 난간이라 누마루·복도각처럼 마루 가장자리에 두르는 것이다.
    axis='x' 면 x0→x1 구간, 'y' 면 y 를 세로축으로 본다.
    """
    pal = pal or DANCHEONG
    bm = bmesh.new()
    span = abs(x1 - x0)
    n = max(2, int(round(span / post_gap)))

    def at(t):
        v = x0 + (x1 - x0) * t
        return (v, y) if axis == 'x' else (y, v)

    for i in range(n + 1):
        px, py = at(i / n)
        # 하엽동자 — 짧은 난간 기둥
        bm_box(bm, px, py, z0 + height * 0.45, 0.11, 0.11, height * 0.9)
    cx, cy = at(0.5)
    sx, sy = (span, 0.10) if axis == 'x' else (0.10, span)
    # 궁판 — 아래쪽 판
    bm_box(bm, cx, cy, z0 + height * 0.20, sx, sy, height * 0.34)
    # 돌란대 — 위쪽 손잡이
    hx, hy = (span, 0.16) if axis == 'x' else (0.16, span)
    bm_box(bm, cx, cy, z0 + height * 0.92, hx, hy, 0.12)

    return bm_to_object(bm, name + "_계자난간", pal['frame'], coll)


def build_walls(name, coll, xs, ys, z0, height, sill=0.0, bar_pitch=0.135,
                pal=None):
    """분합문 벽체 — 창호지 + 띠살 창살 + 상하 인방.

    sill 이 0보다 크면 그만큼 머름(하부 판벽)을 두어 창(窓) 처럼 보이게 한다.
    """
    pal = pal or DANCHEONG
    bm_paper = bmesh.new()
    bm_bar = bmesh.new()
    bm_frame = bmesh.new()

    z_bot = z0 + 0.34 + sill
    z_top = z0 + height * 0.93
    ph = z_top - z_bot                       # 창호 높이

    def panel(cx, cy, span, axis):
        """axis='x' 면 폭이 x 방향(전후면), 'y' 면 y 방향(측면)."""
        w = span * 0.90
        sx, sy = (w, 0.10) if axis == 'x' else (0.10, w)
        fx, fy = (span, 0.30) if axis == 'x' else (0.30, span)

        bm_box(bm_paper, cx, cy, (z_bot + z_top) / 2, sx, sy, ph)
        bm_box(bm_frame, cx, cy, z0 + 0.17, fx, fy, 0.34)          # 하인방
        bm_box(bm_frame, cx, cy, z_top + 0.13, fx, fy, 0.30)       # 상인방
        if sill > 0:                                                # 머름
            bm_box(bm_frame, cx, cy, z0 + 0.34 + sill / 2,
                   fx * 0.95, fy * 0.95, sill)

        # 세로 창살
        n = max(2, int(w / bar_pitch))
        for i in range(n + 1):
            t = -w / 2 + w * i / n
            bx, by = (cx + t, cy) if axis == 'x' else (cx, cy + t)
            bsx, bsy = (0.045, 0.20) if axis == 'x' else (0.20, 0.045)
            bm_box(bm_bar, bx, by, (z_bot + z_top) / 2, bsx, bsy, ph)

        # 가로 창살 — 띠살문답게 위/가운데/아래에 세 줄씩 몰아 짠다
        for base in (0.10, 0.50, 0.88):
            for k in range(3):
                r = base + k * 0.038
                if not 0.02 < r < 0.98:
                    continue
                hsx, hsy = (w, 0.20) if axis == 'x' else (0.20, w)
                bm_box(bm_bar, cx, cy, z_bot + ph * r, hsx, hsy, 0.045)

        # 문설주 — 칸 양옆 수직 테두리
        for s in (-1, 1):
            ex, ey = ((cx + s * span / 2, cy) if axis == 'x'
                      else (cx, cy + s * span / 2))
            esx, esy = (0.16, 0.30) if axis == 'x' else (0.30, 0.16)
            bm_box(bm_frame, ex, ey, (z0 + z_top) / 2, esx, esy, z_top - z0)

    for i in range(len(xs) - 1):
        cx = (xs[i] + xs[i + 1]) / 2.0
        span = xs[i + 1] - xs[i]
        panel(cx, ys[0], span, 'x')
        panel(cx, ys[-1], span, 'x')
    for j in range(len(ys) - 1):
        cy = (ys[j] + ys[j + 1]) / 2.0
        span = ys[j + 1] - ys[j]
        panel(xs[0], cy, span, 'y')
        panel(xs[-1], cy, span, 'y')

    return (bm_to_object(bm_paper, name + "_창호지", pal['paper'], coll),
            bm_to_object(bm_bar, name + "_창살", pal['lattice'], coll),
            bm_to_object(bm_frame, name + "_인방", pal['frame'], coll))
