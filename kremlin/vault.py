# -*- coding: utf-8 -*-
"""교차볼트(крестовый свод) — 실내 천장.

`dome.py` 는 전부 외부용이다(양파돔·텐트지붕·코코시닉·자코마라·아케이드 띠).
실내로 들어오면서 볼트가 필요해졌는데 그게 없어서 여기 만든다.

**min 이 아니라 max 다.** 정사각 베이 위에 반경이 같은 원통 볼트 둘을
직교로 걸었을 때,

    교차볼트   z = z0 + max(√(r²-u²), √(r²-v²))
    클로이스터  z = z0 + min(√(r²-u²), √(r²-v²))

로 갈린다. `min` 을 쓰면 네 변 **전체**에서 볼트가 솟아 벽을 따라 z0 인
수평선이 생기고, 그 결과 **네 변의 반원 아치가 사라진다**. 파세트궁은
Табл.12 평면에 중앙 기둥에서 네 모서리로 뻗는 점선(=능선)이 그려져 있고
단면에 반원 아치 둘이 보이므로 교차볼트가 맞다. 따라서 `max` 다.

**그런데 max 를 축정렬 격자에 그대로 얹으면 안 된다.** 능선이 대각선인데
격자가 축을 따라가서, 능선이 셀을 지그재그로 가로지르며 표면에 계단 자국을
남긴다. 실제로 처음에 그렇게 짰다가 렌더에서 계단이 보였다.
→ 네 개의 **삼각 웹**으로 나눠 능선에 맞춘 부채꼴로 깐다. `_web` 참조.

파세트궁에서 숫자가 딱 닫힌다 — 홀 22.4 m, 베이 11.2 m, r = 5.6 m,
스프링잉 3.4 m, 마루 3.4 + 5.6 = **9.0 m** 로 문헌값과 같다.
"""

import math

import bmesh

import hanok

# 웹을 놓는 네 방향. (u, v) → (x, y).
#   |u| > |v| 인 구역이라 볼트면이 z = √(r²-v²) 로 u 와 무관하다.
_PLACES = (
    lambda u, v: ( u,  v),
    lambda u, v: (-u,  v),
    lambda u, v: ( v,  u),
    lambda u, v: ( v, -u),
)


def _web(bm, place, cx, cy, r, z0, dz, n, m, rv=None, rise=None):
    """능선에서 한 변까지 뻗는 삼각 웹 하나. 행 목록을 돌려준다.

    i=0 은 마루 한 점, i=n 은 변의 아치 전체다. 경계 v = ±u 가 정확히
    능선이 되므로 이웃 웹과 정점이 맞물린다.

    `rv` 와 `rise` 를 주면 **직사각 베이**가 된다 — 원통 둘의 반경이 달라도
    마루를 같은 높이로 맞추려면 원이 아니라 타원 단면을 써야 한다:
        z = rise · √(1 - (v/rv)²)
    정사각이면 rv = r = rise 라 원으로 돌아온다.
    """
    rv = r if rv is None else rv
    rise = r if rise is None else rise
    rows = []
    for i in range(n + 1):
        u = r * i / n
        cnt = 1 if i == 0 else m + 1
        row = []
        for j in range(cnt):
            # 능선은 |v|/rv = |u|/r 이므로 u 를 rv/r 로 환산해 훑는다
            v = 0.0 if i == 0 else (-u + 2.0 * u * j / m) * (rv / r)
            a = 1.0 - (v / rv) ** 2
            z = z0 + rise * (math.sqrt(a) if a > 0.0 else 0.0) + dz
            x, y = place(u, v)
            row.append(bm.verts.new((cx + x, cy + y, z)))
        rows.append(row)
    return rows


def _stitch(bm, rows, flip=False):
    """부채꼴 행들을 잇는다. 첫 행은 한 점이라 삼각형이 된다."""
    for i in range(len(rows) - 1):
        a, b = rows[i], rows[i + 1]
        if len(a) == 1:
            for j in range(len(b) - 1):
                f = (a[0], b[j], b[j + 1])
                bm.faces.new(f[::-1] if flip else f)
        else:
            for j in range(len(a) - 1):
                f = (a[j], a[j + 1], b[j + 1], b[j])
                bm.faces.new(f[::-1] if flip else f)


def groin(bm, cx, cy, z0, side, seg=16, thick=0.35, side_v=None, rise=None):
    """베이 하나 위의 교차볼트. 정사각이 기본이고 직사각도 받는다.

    cx, cy   베이 중심
    z0       스프링잉 높이 (네 모서리가 앉는 높이)
    side     베이 한 변 (u 방향). 마루는 기본으로 z0 + side/2
    side_v   v 방향 변. 생략하면 정사각
    rise     마루 높이. 생략하면 side/2 (정사각 반원)
    seg      능선 방향 분할. 변 방향은 그 두 배
    thick    껍질 두께. 0 이면 안쪽 면만
    """
    r = side / 2.0
    rv = r if side_v is None else side_v / 2.0
    rz = r if rise is None else rise
    n, m = seg, seg * 2
    for k, place in enumerate(_PLACES):
        swap = k >= 2                       # 뒤 둘은 u/v 가 바뀐 방향이다
        ra, rb = (rv, r) if swap else (r, rv)
        inner = _web(bm, place, cx, cy, ra, z0, 0.0, n, m, rv=rb, rise=rz)
        _stitch(bm, inner)
        if thick <= 0.0:
            continue
        outer = _web(bm, place, cx, cy, ra, z0, thick, n, m, rv=rb, rise=rz)
        _stitch(bm, outer, flip=True)
        # 변 쪽 아치 테두리만 막으면 껍질이 닫힌다 (능선은 이웃 웹과 맞물린다)
        a, b = inner[-1], outer[-1]
        for j in range(len(a) - 1):
            bm.faces.new((a[j], b[j], b[j + 1], a[j + 1]))
    return z0 + rz


def barrel(bm, cx, cy, z0, span, length, along_v=True, seg=20, thick=0.3,
           yaw_c=1.0, yaw_s=0.0):
    """원통 볼트. 반원 단면이 length 만큼 곧게 이어진다.

    교차볼트를 여러 칸 늘어놓으면 **칸 경계마다 아치가 각각 내려앉아 그 위가
    뚫린다.** 좁고 긴 공간에서는 경계가 없는 원통 하나가 확실하다.
    (сени 에서 정사각→직사각→횡단띠로 세 번 시도하고 이걸로 왔다.)

    yaw_c, yaw_s 는 cos/sin 으로, 로컬 축을 월드로 돌린다.
    """
    r = span / 2.0
    half = length / 2.0

    def W(a, b):
        return (cx + a * yaw_c - b * yaw_s, cy + a * yaw_s + b * yaw_c)

    rings = []
    for d in (0.0, thick):
        rows = []
        for k in range(seg + 1):
            th = math.pi * k / seg
            u = -r * math.cos(th)
            z = z0 + (r + d) * math.sin(th)
            row = []
            for s in (-half, half):
                a, b = (u, s) if along_v else (s, u)
                x, y = W(a, b)
                row.append(bm.verts.new((x, y, z)))
            rows.append(row)
        rings.append(rows)
        if thick <= 0.0:
            break
    inner = rings[0]
    for k in range(seg):
        bm.faces.new((inner[k][0], inner[k][1], inner[k + 1][1], inner[k + 1][0]))
    if thick > 0.0:
        outer = rings[1]
        for k in range(seg):
            bm.faces.new((outer[k + 1][0], outer[k + 1][1], outer[k][1], outer[k][0]))
        for j in (0, 1):
            for k in range(seg):
                a, b = inner[k][j], inner[k + 1][j]
                c, d2 = outer[k + 1][j], outer[k][j]
                f = (a, b, c, d2) if j == 0 else (d2, c, b, a)
                bm.faces.new(f)
    return z0 + r


def quad_groin(bm, cx, cy, z0, hall, seg=16, thick=0.35):
    """중앙 기둥 하나에 네 베이가 모이는 구성 — 파세트궁 홀.

    hall 은 홀 **안목** 한 변. 베이는 그 절반이고 마루는 z0 + hall/4 다.
    돌려주는 값은 (마루 높이, 베이 한 변).
    """
    bay = hall / 2.0
    off = bay / 2.0
    crown = z0
    for sx in (-1, 1):
        for sy in (-1, 1):
            crown = groin(bm, cx + sx * off, cy + sy * off, z0, bay,
                          seg=seg, thick=thick)
    return crown, bay


def pier(bm, cx, cy, z0, z1, side, cap_h=0.55, cap_out=0.30, base_h=0.45,
         base_out=0.34):
    """볼트를 받는 사각 기둥. 주두와 초석이 조금씩 내밀어 그림자선을 만든다.

    통짜 각기둥으로 두면 흰 막대로 보인다 — 성벽 여장에서 들이밈이 없으면
    흰 판자가 되는 것과 같은 문제다.
    """
    shaft_z0 = z0 + base_h
    shaft_z1 = z1 - cap_h
    hanok.bm_box(bm, cx, cy, (z0 + shaft_z0) / 2.0,
                 side + base_out * 2, side + base_out * 2, shaft_z0 - z0)
    hanok.bm_box(bm, cx, cy, (shaft_z0 + shaft_z1) / 2.0, side, side,
                 shaft_z1 - shaft_z0)
    hanok.bm_box(bm, cx, cy, (shaft_z1 + z1) / 2.0,
                 side + cap_out * 2, side + cap_out * 2, z1 - shaft_z1)


def build_test(coll=None, seg=16):
    """견본 — 홀 한 칸을 그대로 세워 본다."""
    from kremlin import measured
    from kremlin.measured import val

    coll = coll or hanok.new_collection("크렘린_볼트_견본")
    hall = val(measured.GRANOVITAYA, 'hall_inner')
    z0 = val(measured.GRANOVITAYA, 'vault_spring_h')
    side = val(measured.GRANOVITAYA, 'pier_side')

    bm = bmesh.new()
    crown, bay = quad_groin(bm, 0.0, 0.0, z0, hall, seg=seg, thick=0.35)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    hanok.bm_to_object(bm, "견본_볼트", 'plaster', coll)

    bm = bmesh.new()
    pier(bm, 0.0, 0.0, 0.0, z0, side)
    hanok.bm_to_object(bm, "견본_기둥", 'granite', coll)
    return {'crown': crown, 'bay': bay, 'spring': z0, 'hall': hall}
