# -*- coding: utf-8 -*-
"""크렘린 재질 — Poly Haven CC0 텍스처를 팔레트 재질에 물린다.

hanok.PALETTE 는 단색 Principled 다. 오버데어는 Color3 만 받으므로 그대로
써야 하지만, 블렌더 렌더에서는 텍스처가 있어야 벽이 판때기로 안 보인다.
그래서 **팔레트 색은 유지한 채 텍스처를 곱한다**(MixRGB MULTIPLY).
색을 텍스처로 갈아치우면 오버데어로 나가는 Color3 와 렌더가 어긋난다.

에셋 (전부 CC0 — 출처 표시 의무조차 없다)
    brick_wall_006          성벽·탑 붉은 벽돌
    castle_wall_slates      석재 성벽 (예비)
    plastered_stone_wall    성당 백석
    green_metal_rust        녹청 금속 지붕
    cobblestone_floor_08    붉은광장 자갈 포장
    approaching_storm       HDRI — 모스크바 특유의 흐린 하늘

────────────────────────────────────────────────────────────────────
terrain.py 가 남긴 함정 세 개를 그대로 피한다
────────────────────────────────────────────────────────────────────
1. **Mapping 의 vector_type 을 반드시 'POINT' 로 못박는다.**
   Poly Haven 애드온은 이걸 'TEXTURE' 로 만들어 두는데, 그 모드에서 Scale 은
   **나누기**로 먹는다. 2.5 m 타일을 노린 scale 0.4 가 실제로는 0.4 m 타일이
   되어 단색 판때기로 보였다.
2. **nor_gl 을 쓴다.** nor_dx 를 그대로 물리면 요철이 반대로 파인다.
   두 맵이 다 딸려 오므로 이름으로 골라야 한다.
3. UV 가 없다. 우리 메시는 bmesh 로 구웠고 UV 레이어가 없다.
   → **오브젝트 좌표 + BOX 투영**(삼면 투영)을 쓴다. 평면 투영으로 두면
   수직 벽면에서 텍스처가 세로로 늘어진다.
"""

import bpy

# (팔레트 재질 이름, PolyHaven 에셋, 타일 간격 m, 텍스처 세기 0~1)
#
# **밝기 정규화가 핵심이다.** 텍스처를 팔레트 색에 그냥 곱하면 결과가 두 번
# 어두워진다(텍스처 평균 0.2 대 × 팔레트색). 처음에 그렇게 만들어서 렌더에서
# GUM(백석 0.72)이 시커멓게 나왔다.
#   → 텍스처를 **평균이 1.0 이 되게 증폭**한 뒤 팔레트 색을 곱한다.
#     그래야 「색은 팔레트 그대로, 텍스처는 명암 변조만」이 된다.
#
# 게인을 손으로 넣었더니 또 틀렸다(백석이 여전히 30% 어두웠다). 에셋마다 평균이
# 다르기 때문이다. → **이미지 픽셀을 실제로 재서 게인을 자동 산출**한다.
# 세기(amount)는 텍스처가 팔레트 색을 얼마나 흔들지다. 0 이면 순수 단색,
# 1 이면 텍스처 그대로. 백석처럼 얼룩이 심한 텍스처는 낮춰야 흰 돌로 읽힌다.
SURFACES = [
    ("MAT_크렘린_벽돌",     "brick_wall_006",       2.4, 0.85),
    ("MAT_크렘린_벽돌_암",   "brick_wall_006",       2.4, 0.85),
    ("MAT_백석",           "plastered_stone_wall", 3.2, 0.45),
    ("MAT_녹청지붕",        "green_metal_rust",     2.8, 0.70),
    ("MAT_화강암_어둡",      "cobblestone_floor_08", 2.6, 0.80),
    ("MAT_적화강암",        "castle_wall_slates",   1.8, 0.75),
]

# 파세트궁 실내(kremlin/interior.py) 전용. 외피 목록과 섞지 않는다 — 타일
# 간격이 완전히 다르다. 실내는 눈에서 2~10 m 라 외벽(2.4~3.2 m 타일)을 그대로
# 쓰면 무늬가 커서 벽지처럼 보인다.
#
# ⚠ **세기(amount)를 낮게 잡는다.** 프레스코 바탕은 「고른 황토 면」이 맞고
#   회벽 얼룩이 세면 낡은 창고가 된다. 반대로 아랫층 석조는 세게 준다 —
#   거기가 거친 게 위층과의 대비를 만든다.
SURFACES_INTERIOR = [
    ("MAT_프레스코_황", "beige_wall_001",       1.8, 0.35),
    ("MAT_프레스코_적", "beige_wall_001",       1.8, 0.30),
    # 대홀 바닥은 **다듬은 석판**이다. 처음에 자갈(cobblestone)을 썼더니
    # 방이 아니라 길바닥으로 읽혔다 — 실내에서 무늬 스케일이 맞아도 재료가
    # 옥외용이면 그것만으로 실내감이 깨진다.
    ("MAT_바닥석",     "stone_embedded_tiles", 2.2, 0.70),
    ("MAT_바닥거친",   "cobblestone_floor_08", 1.4, 0.85),   # 아랫층은 거친 게 맞다
    ("MAT_하층석조",   "castle_wall_slates",   1.6, 0.85),
    ("MAT_백석",       "plastered_stone_wall", 2.0, 0.45),
]

_MEAN_CACHE = {}


def _mean_luma(img, step=37):
    """이미지 평균 밝기. 픽셀을 성기게 훑는다.

    2048² × 4 채널을 전부 읽으면 느리다. 소수 간격으로 건너뛰면 타일 격자와
    공명하지 않아 성긴 표본으로도 평균이 잘 잡힌다.
    sRGB jpg 이므로 대략적인 감마 역보정(2.2 승)을 해서 선형 평균을 낸다.
    """
    key = img.name
    if key in _MEAN_CACHE:
        return _MEAN_CACHE[key]
    px = img.pixels[:]
    n = len(px) // 4
    if n == 0:
        return 0.22
    tot, cnt = 0.0, 0
    for i in range(0, n, step):
        j = i * 4
        tot += 0.2126 * px[j] + 0.7152 * px[j + 1] + 0.0722 * px[j + 2]
        cnt += 1
    m = max(1e-4, tot / max(1, cnt))
    _MEAN_CACHE[key] = m
    return m

WORLD_HDRI = "approaching_storm"


def _images_of(asset_id):
    """받아 둔 PolyHaven 재질에서 이미지 데이터블록을 종류별로 찾는다."""
    out = {}
    mat = bpy.data.materials.get(asset_id)
    if mat and mat.use_nodes:
        for n in mat.node_tree.nodes:
            if n.type != 'TEX_IMAGE' or not n.image:
                continue
            nm = n.image.name.lower()
            if 'nor_gl' in nm:
                out['normal'] = n.image
            elif 'nor_dx' in nm:
                out.setdefault('normal_dx', n.image)
            elif 'diff' in nm or 'col' in nm:
                out['diffuse'] = n.image
            elif 'rough' in nm and 'ao' not in nm:
                out['rough'] = n.image
            elif nm.endswith('arm') or '_arm' in nm:
                out['arm'] = n.image
    # 이미지 이름으로 한 번 더 훑는다 (재질이 지워졌을 때 대비)
    for img in bpy.data.images:
        nm = img.name.lower()
        if not nm.startswith(asset_id.lower()):
            continue
        if 'nor_gl' in nm:
            out.setdefault('normal', img)
        elif 'diff' in nm:
            out.setdefault('diffuse', img)
        elif 'rough' in nm and 'ao' not in nm:
            out.setdefault('rough', img)
    return out


def apply(tile_default=2.5, normal_strength=0.8, surfaces=None):
    """팔레트 재질에 텍스처를 물린다. (적용, 건너뜀) 반환.

    `surfaces` 를 주면 그 목록을 쓴다 — 실내는 `SURFACES_INTERIOR`.
    """
    done, skipped = [], []
    for mat_name, asset, tile, amount in (surfaces or SURFACES):
        mat = bpy.data.materials.get(mat_name)
        if mat is None:
            skipped.append((mat_name, "팔레트 재질 없음"))
            continue
        imgs = _images_of(asset)
        if 'diffuse' not in imgs:
            skipped.append((mat_name, "%s diffuse 없음" % asset))
            continue

        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        if bsdf is None:
            skipped.append((mat_name, "Principled 없음"))
            continue
        base_rgb = tuple(bsdf.inputs["Base Color"].default_value)[:3]

        # 이 재질에 예전에 깔았던 텍스처 노드를 걷어낸다 (재실행 안전)
        for n in list(nt.nodes):
            if n.type in ('TEX_IMAGE', 'MAPPING', 'TEX_COORD', 'NORMAL_MAP', 'MIX_RGB'):
                nt.nodes.remove(n)

        coord = nt.nodes.new('ShaderNodeTexCoord')
        coord.location = (-1000, 0)
        mapn = nt.nodes.new('ShaderNodeMapping')
        mapn.location = (-800, 0)
        # ★ POINT 로 못박는다. TEXTURE 모드에서는 Scale 이 나누기로 먹는다.
        mapn.vector_type = 'POINT'
        s = 1.0 / max(0.05, tile or tile_default)
        mapn.inputs['Scale'].default_value = (s, s, s)
        nt.links.new(coord.outputs['Object'], mapn.inputs['Vector'])

        def tex(img, loc, non_color=False):
            t = nt.nodes.new('ShaderNodeTexImage')
            t.image = img
            t.location = loc
            t.projection = 'BOX'          # UV 가 없다 → 삼면 투영
            t.projection_blend = 0.25
            if non_color:
                t.image.colorspace_settings.name = 'Non-Color'
            nt.links.new(mapn.outputs['Vector'], t.inputs['Vector'])
            return t

        d = tex(imgs['diffuse'], (-660, 220))
        # ① 실측 평균으로 게인을 잡아 텍스처를 평균 1.0 으로 정규화
        mean = _mean_luma(imgs['diffuse'])
        gain = 1.0 / mean
        norm = nt.nodes.new('ShaderNodeMixRGB')
        norm.blend_type = 'MULTIPLY'
        norm.location = (-460, 220)
        norm.inputs['Fac'].default_value = 1.0
        norm.inputs['Color2'].default_value = (gain, gain, gain, 1.0)
        nt.links.new(d.outputs['Color'], norm.inputs['Color1'])
        # ② 세기 조절 — 흰색과 정규화 텍스처 사이를 amount 로 보간
        soft = nt.nodes.new('ShaderNodeMixRGB')
        soft.blend_type = 'MULTIPLY'
        soft.location = (-300, 220)
        soft.inputs['Fac'].default_value = amount
        soft.inputs['Color1'].default_value = (1.0, 1.0, 1.0, 1.0)
        nt.links.new(norm.outputs['Color'], soft.inputs['Color2'])
        # ③ 팔레트 색을 곱한다 → 색은 팔레트, 명암 변조는 텍스처
        mix = nt.nodes.new('ShaderNodeMixRGB')
        mix.blend_type = 'MULTIPLY'
        mix.location = (-140, 220)
        mix.inputs['Fac'].default_value = 1.0
        nt.links.new(soft.outputs['Color'], mix.inputs['Color1'])
        mix.inputs['Color2'].default_value = (base_rgb[0], base_rgb[1],
                                              base_rgb[2], 1.0)
        nt.links.new(mix.outputs['Color'], bsdf.inputs["Base Color"])

        if 'rough' in imgs:
            r = tex(imgs['rough'], (-520, -40), non_color=True)
            nt.links.new(r.outputs['Color'], bsdf.inputs["Roughness"])
        if 'normal' in imgs:                      # ★ nor_gl. nor_dx 는 반대로 판다
            nmap_tex = tex(imgs['normal'], (-520, -320), non_color=True)
            nmap = nt.nodes.new('ShaderNodeNormalMap')
            nmap.location = (-240, -320)
            nmap.inputs['Strength'].default_value = normal_strength
            nt.links.new(nmap_tex.outputs['Color'], nmap.inputs['Color'])
            nt.links.new(nmap.outputs['Normal'], bsdf.inputs["Normal"])

        done.append((mat_name, asset, "nor_gl" if 'normal' in imgs else "노멀없음",
                     base_rgb, mean, gain, amount))
    return done, skipped


def setup_world(strength=1.0, rotation_deg=-35.0):
    """HDRI 월드. 금박 돔은 반사가 전부라 하늘이 결과를 좌우한다.

    ⚠ **Poly Haven 애드온은 HDRI 를 임시 파일에 쓴다.** 받아 보니 이미지
    이름이 `tmpggtzq1jn.hdr` 이고 경로가 `%LOCALAPPDATA%\\Temp` 였다.
      · 이름으로 에셋을 찾을 수 없다 → 환경 텍스처 노드의 **존재**로 찾는다.
      · temp 가 청소되면 .blend 를 다시 열었을 때 링크가 깨진다
        → **pack() 으로 .blend 안에 넣는다.** 이게 이 함수의 핵심 부수효과다.
    """
    import math
    w = None
    for cand in bpy.data.worlds:
        if not cand.use_nodes:
            continue
        if any(n.type == 'TEX_ENVIRONMENT' and n.image
               for n in cand.node_tree.nodes):
            w = cand
            break
    if w is None:
        return None
    bpy.context.scene.world = w
    # 임시 파일 의존을 끊는다
    for n in w.node_tree.nodes:
        if n.type == 'TEX_ENVIRONMENT' and n.image:
            if not n.image.packed_file:
                try:
                    n.image.pack()
                except Exception as exc:            # noqa: BLE001
                    print("HDRI pack 실패: %s" % exc)
            if n.image.name.startswith('tmp'):
                n.image.name = "hdri_%s" % WORLD_HDRI
    nt = w.node_tree
    bg = next((n for n in nt.nodes if n.type == 'BACKGROUND'), None)
    if bg:
        bg.inputs[1].default_value = strength
    env = next((n for n in nt.nodes if n.type == 'TEX_ENVIRONMENT'), None)
    if env:
        mp = next((n for n in nt.nodes if n.type == 'MAPPING'), None)
        if mp is None:
            coord = nt.nodes.new('ShaderNodeTexCoord')
            mp = nt.nodes.new('ShaderNodeMapping')
            nt.links.new(coord.outputs['Generated'], mp.inputs['Vector'])
            nt.links.new(mp.outputs['Vector'], env.inputs['Vector'])
        mp.inputs['Rotation'].default_value[2] = math.radians(rotation_deg)
    return w.name
