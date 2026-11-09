# -*- coding: utf-8 -*-
"""크렘린 렌더 — 샷 테이블 + Cycles 설정.

render.py 규약을 따른다:
  · 카메라 방향은 **오일러를 손으로 넣지 않고 '바라볼 지점'으로 지정**한다.
    각도를 손으로 넣으면 틀리기 쉽다.
  · **clip_end 를 20000 으로.** 기본 100 m 면 전경 샷이 통째로 잘린다.
    실제로 당한 적이 있다.
  · view_transform 은 AgX → Filmic → Standard 순으로 시도한다.

조명은 HDRI(approaching_storm)가 주광이다. 금박 돔은 반사가 전부라
하늘이 결과를 좌우한다 — 구름 있는 HDRI 를 고른 이유다.
태양은 그림자만 만들도록 약하게 둔다(이중광원이 되면 대비가 무너진다).
"""

import math
import os

import bpy
from mathutils import Vector

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# 이름: (카메라 위치, 바라볼 지점, 렌즈 mm)
SHOTS = {
    "01_붉은광장_성바실리": ((520.0, -95.0, 26.0), (300.0, 110.0, 40.0), 35.0),
    "02_스파스카야_정면": ((430.0, 40.0, 22.0), (205.0, 100.0, 42.0), 50.0),
    "03_성당광장": ((60.0, -200.0, 46.0), (-50.0, -110.0, 30.0), 40.0),
    "04_강건너_전경": ((240.0, -900.0, 120.0), (-90.0, -180.0, 40.0), 55.0),
    "05_성벽_눈높이": ((-150.0, -345.0, 5.5), (-235.0, -330.0, 12.0), 35.0),
    "06_부감": ((820.0, -620.0, 400.0), (20.0, 30.0, 30.0), 50.0),
}


def setup(res=(1600, 900), samples=96, gpu=True):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.cycles.transparent_max_bounces = 4
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        for t in ('OPTIX', 'CUDA', 'HIP', 'ONEAPI'):
            try:
                prefs.compute_device_type = t
                break
            except Exception:                      # noqa: BLE001
                continue
        prefs.get_devices()
        n_gpu = 0
        for d in prefs.devices:
            d.use = (d.type != 'CPU')
            n_gpu += 1 if d.type != 'CPU' else 0
        sc.cycles.device = 'GPU' if (gpu and n_gpu) else 'CPU'
    except Exception as exc:                       # noqa: BLE001
        print("GPU 설정 실패, CPU 로: %s" % exc)
        sc.cycles.device = 'CPU'

    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    for tv in ('AgX', 'Filmic', 'Standard'):
        try:
            sc.view_settings.view_transform = tv
            break
        except Exception:                          # noqa: BLE001
            continue
    sc.view_settings.exposure = (-0.35 if sc.view_settings.view_transform == 'AgX'
                                 else -0.7)
    return sc.cycles.device, sc.view_settings.view_transform


def camera():
    cam = bpy.data.objects.get("KR_Cam")
    if cam is None:
        cd = bpy.data.cameras.new("KR_Cam")
        cam = bpy.data.objects.new("KR_Cam", cd)
        bpy.context.scene.collection.objects.link(cam)
    # ★ 기본 far clip 100 m 면 전경 샷이 통째로 잘린다
    cam.data.clip_start, cam.data.clip_end = 0.5, 20000.0
    bpy.context.scene.camera = cam
    return cam


def aim(cam, loc, at, lens=42.0):
    """오일러 대신 '바라볼 지점'으로 방향을 준다."""
    cam.location = Vector(loc)
    d = Vector(at) - Vector(loc)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    return cam


def render_all(only=None, out_dir=None, res=(1600, 900), samples=96):
    out_dir = out_dir or OUT_DIR
    dev, tv = setup(res=res, samples=samples)
    cam = camera()
    made = []
    for name, (loc, at, lens) in SHOTS.items():
        if only and name not in only:
            continue
        aim(cam, loc, at, lens)
        path = os.path.join(out_dir, "%s.png" % name)
        bpy.context.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        made.append((name, path, os.path.getsize(path)))
        print("  렌더 완료 %s" % name)
    return made, dev, tv
