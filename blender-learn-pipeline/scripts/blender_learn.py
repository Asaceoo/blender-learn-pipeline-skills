# blender_learn.py — Blender 无头渲染助手库（blender-learn-pipeline 技能核心）
# 版本见 VERSION 文件；用法见 references/blender-headless.md
# 单独 --python 运行本文件 = 渲染「知识体系塔」演示场景
#
# 兼容性：Blender 5.x 实测通过；≤4.x 的 fcurves / FFMPEG 两条旧路径保留兼容分支
import bpy
import sys
import os
import math
import glob

VERSION = "1.1.0"

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    r"C:\Windows\Fonts\arial.ttf",
]
_FONT_CACHE = None

# 各类型灯光的合理默认能量（SUN 无单位 / AREA·POINT 为瓦特）
_LIGHT_DEFAULT_ENERGY = {'SUN': 3.0, 'AREA': 300.0, 'POINT': 100.0, 'SPOT': 100.0}


def _err(msg):
    """ stderr 输出，避免个别控制台中文编码崩溃。"""
    try:
        sys.stderr.write(msg + "\n")
    except Exception:
        pass


def load_cjk_font():
    """按候选顺序加载支持中文的系统字体，失败返回 None（用默认字体）。"""
    global _FONT_CACHE
    if _FONT_CACHE is not None:
        return _FONT_CACHE
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                _FONT_CACHE = bpy.data.fonts.load(path)
                return _FONT_CACHE
            except Exception:
                continue
    _err("WARN: no CJK font found, labels may show boxes")
    return None


def clear_scene():
    """清空所有对象与孤儿数据，保证脚本可重复运行。"""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for block in (bpy.data.meshes, bpy.data.curves, bpy.data.materials,
                  bpy.data.lights, bpy.data.cameras):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def setup_world(color=(0.92, 0.93, 0.95, 1.0), strength=1.0):
    """浅灰世界背景：避免纯黑底 + 给 Cycles 环境光。"""
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = color
    bg.inputs["Strength"].default_value = strength


def add_light(name, type_='SUN', energy=None, location=(4, -4, 6),
              rotation=(math.radians(50), 0, math.radians(30))):
    """创建灯光。energy 缺省时按类型取合理默认（AREA/POINT 瓦特数远大于 SUN）。"""
    light = bpy.data.lights.new(name, type=type_)
    light.energy = _LIGHT_DEFAULT_ENERGY.get(type_, 3.0) if energy is None else energy
    obj = bpy.data.objects.new(name, light)
    obj.location = location
    obj.rotation_euler = rotation
    bpy.context.collection.objects.link(obj)
    return obj


def add_material(name, color, roughness=0.45, metallic=0.0):
    """按名复用材质，避免重复创建同名堆积。"""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def add_box(name, size, location, color, rotation=(0, 0, 0)):
    """实心块体：层次塔 / 管段 / 机制件的基本单元。size=(x, y, z)。"""
    bpy.ops.mesh.primitive_cube_add(location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    obj.data.materials.append(add_material(name + "_mat", color, roughness=0.55))
    return obj


def add_label(body, location, size=0.42, color=(0.08, 0.08, 0.08),
              name=None, vertical=True, rotation_z=0.0):
    """文字标注。vertical=True 时正面朝 -Y（面向主/等轴相机）。
    用纯漫反射深色材质——不要用发光材质，发光文字会在块体表面
    产生粗糙镜面反射重影（真机实测坑）。"""
    name = name or ("label_" + body)
    curve = bpy.data.curves.new(name + "_curve", type='FONT')
    curve.body = body
    curve.size = size
    curve.align_x = 'CENTER'
    curve.align_y = 'CENTER'
    font = load_cjk_font()
    if font is not None:
        curve.font = font
    obj = bpy.data.objects.new(name, curve)
    obj.location = location
    if vertical:
        obj.rotation_euler = (math.radians(90), 0, rotation_z)
    else:
        obj.rotation_euler = (0, 0, rotation_z)
    obj.data.materials.append(add_material(name + "_mat", color, roughness=0.8))
    bpy.context.collection.objects.link(obj)
    # 关键：悬空文字既不能被镜面反射成像，也不能往块体上投影，
    # 否则块体表面会出现可读的「文字重影」（真机实测坑：两者都会出现）
    obj.visible_glossy = False
    obj.visible_shadow = False
    return obj


def add_camera(name="Camera", location=(7, -7, 5), target=(0, 0, 1)):
    """创建相机并用 TRACK_TO 约束对准目标空物体。返回 (相机, 目标空物体)。"""
    cam = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, cam)
    obj.location = location
    bpy.context.collection.objects.link(obj)
    tgt = bpy.data.objects.new(name + "_target", None)
    tgt.location = target
    bpy.context.collection.objects.link(tgt)
    con = obj.constraints.new('TRACK_TO')
    con.target = tgt
    con.track_axis = 'TRACK_NEGATIVE_Z'
    con.up_axis = 'UP_Y'
    bpy.context.scene.camera = obj
    return obj, tgt


def setup_render(engine='CYCLES', samples=48, res=(1280, 720)):
    """渲染全局配置。samples/res 由调用方保证 >=1 / 正数。"""
    sc = bpy.context.scene
    sc.render.engine = engine
    if engine == 'CYCLES':
        sc.cycles.samples = samples
        sc.cycles.use_denoising = True
        sc.cycles.device = 'CPU'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = 'Standard'  # AgX 会洗灰颜色
    sc.render.image_settings.file_format = 'PNG'


def _check_file(path, kind="产物"):
    """清单兜底：产物必须存在且非 0 字节，否则抛错（不交付伪产物）。"""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise RuntimeError(f"{kind}渲染失败或为空: {path}")


def render_stills(out_dir, views=None, prefix=""):
    """多视角静帧。views: {名称: (相机位置, 目标点)}，默认三视角。
    返回生成的文件路径列表。"""
    os.makedirs(out_dir, exist_ok=True)
    if views is None:
        views = {
            "01-主视角": ((0, -9.5, 2.5), (0, 0, 1.2)),
            "02-等轴视角": ((8, -8, 6.4), (0, 0, 1.0)),
            "03-俯视角": ((0, -0.01, 12), (0, 0, 0)),
        }
    sc = bpy.context.scene
    # 复用一台相机 + 一个目标空物体，逐视角改位（避免对象堆积）
    cam, tgt = add_camera(name="Camera_stills")
    paths = []
    for name, (loc, t) in views.items():
        cam.location = loc
        tgt.location = t
        path = os.path.join(out_dir, prefix + name + ".png")
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        _check_file(path, "静帧")
        paths.append(path)
    return paths


def _linearize(obj, data_path, index):
    """把指定 FCurve 的关键帧改为线性插值。兼容 Blender ≤4.x（action.fcurves）
    与 5.x（分层 slot：layers→strips→channelbags→fcurves）。
    返回改写的关键帧数；0 = 没找到（调用方应视为异常信号而非静默）。"""
    ad = getattr(obj, "animation_data", None)
    action = getattr(ad, "action", None) if ad else None
    if action is None:
        return 0
    fcs = []
    if hasattr(action, "fcurves"):  # Blender ≤ 4.x
        fcs = list(action.fcurves)
    else:  # Blender 5.x slotted actions
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    fcs.extend(bag.fcurves)
    n = 0
    for fc in fcs:
        if fc.data_path == data_path and fc.array_index == index:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
                n += 1
    return n


def render_turntable(out_dir, frames=24, fps=24, radius=9, height=5.5,
                     target=(0, 0, 1.2), prefix="turntable"):
    """360° 环绕镜头：相机挂 pivot 空物体，Z 轴转满一圈，首尾无缝。
    frames>=2、fps>0 由调用方（main）校验。
    输出 [prefix].mp4（Blender 内置 FFMPEG H264）。返回最终 mp4 路径。"""
    if frames < 2:
        raise ValueError("frames 必须 >= 2（环绕至少两帧）")
    if fps <= 0:
        raise ValueError("fps 必须 > 0")
    os.makedirs(out_dir, exist_ok=True)
    # 清掉同前缀旧产物，避免遗留文件干扰下方 glob 归位（真机实测坑）
    for stale in glob.glob(os.path.join(out_dir, prefix + "*.mp4")):
        os.remove(stale)
    sc = bpy.context.scene
    pivot = bpy.data.objects.new("turntable_pivot", None)
    pivot.location = target
    bpy.context.collection.objects.link(pivot)
    cam, _ = add_camera(name="Camera_Turntable",
                        location=(0, -radius, height), target=target)
    # 挂父级必须保留矩阵父逆，否则 location 被重新解释为 pivot 局部坐标，
    # 相机静默跳位（真机实测坑：高度 5.5 被抬到 target_z + 5.5）
    bpy.context.view_layer.update()
    cam.parent = pivot
    cam.matrix_parent_inverse = pivot.matrix_world.inverted()
    sc.frame_start = 1
    sc.frame_end = frames
    sc.render.fps = fps
    pivot.rotation_euler = (0, 0, 0)
    pivot.keyframe_insert(data_path="rotation_euler", index=2, frame=1)
    pivot.rotation_euler.z = math.radians(360)
    pivot.keyframe_insert(data_path="rotation_euler", index=2, frame=frames)
    if _linearize(pivot, "rotation_euler", 2) == 0:
        # 线性插值失败 = 首尾会有缓入缓出，环绕循环会卡顿 → 必须暴露而不是吞掉
        _err("WARN: keyframe linearization found no fcurve, loop may stutter")
    img = sc.render.image_settings
    has_media_type = any(p.identifier == 'media_type' for p in img.bl_rna.properties)
    if has_media_type:
        img.media_type = 'VIDEO'      # Blender 5.x：视频模式经 media_type 切换
    else:
        img.file_format = 'FFMPEG'    # Blender ≤ 4.x
    sc.render.ffmpeg.format = 'MPEG4'
    sc.render.ffmpeg.codec = 'H264'
    sc.render.ffmpeg.constant_rate_factor = 'HIGH'
    sc.render.filepath = os.path.join(out_dir, prefix)
    bpy.ops.render.render(animation=True)
    # Blender 动画输出可能带帧号后缀，归位为单个 [prefix].mp4
    produced = sorted(glob.glob(os.path.join(out_dir, prefix + "*.mp4")))
    if not produced:
        raise RuntimeError(f"环绕渲染未产出 mp4: {out_dir}")
    final = os.path.join(out_dir, prefix + ".mp4")
    if os.path.abspath(produced[0]) != os.path.abspath(final):
        os.replace(produced[0], final)
    _check_file(final, "环绕视频")
    if has_media_type:
        img.media_type = 'IMAGE'
    img.file_format = 'PNG'           # 恢复，保证静帧可续渲染
    return final


# ---------------- 演示场景：知识体系塔（本技能自身的概念做成 3D） ----------------

def build_demo():
    clear_scene()
    setup_world()
    add_light("Key", type_='SUN')
    add_light("Fill", type_='AREA', location=(-5, -6, 5),
              rotation=(math.radians(60), 0, math.radians(-40)))
    layers = [  # 自下而上：延伸层(宽) → 支撑层 → 核心层(窄)
        ("延伸层", (0.30, 0.55, 0.85), (3.8, 3.8, 0.9), 0.45),
        ("支撑层", (0.93, 0.65, 0.15), (3.0, 3.0, 0.9), 1.35),
        ("核心层", (0.85, 0.33, 0.25), (2.2, 2.2, 0.9), 2.25),
    ]
    for name, color, size, z in layers:
        add_box(name, size=size, location=(0, 0, z), color=color)
        add_label(name, location=(0, -size[1] / 2 - 0.55, z), size=0.45)
    add_label("3D 学习流水线", location=(0, 0, 3.3), size=0.5)
    # 底部圆环指示「拆解 → 建体系 → 可视化 → 本质 → 自检」的循环
    bpy.ops.mesh.primitive_torus_add(major_radius=3.1, minor_radius=0.07,
                                     location=(0, 0, 0.07))
    ring = bpy.context.active_object
    ring.name = "流程环"
    ring.data.materials.append(add_material("流程环_mat", (0.25, 0.25, 0.25),
                                            roughness=0.6))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    import argparse
    ap = argparse.ArgumentParser(
        prog="blender_learn",
        description="blender-learn-pipeline 演示渲染；主题场景请 import 本库自行建主体")
    ap.add_argument("--out", required=True, help="输出目录")
    ap.add_argument("--frames", type=int, default=24, help="环绕帧数（>=2），24 帧 @24fps ≈ 1 秒循环")
    ap.add_argument("--samples", type=int, default=48, help="Cycles 采样数（>=1）")
    ap.add_argument("--fps", type=int, default=24, help="环绕视频帧率")
    ap.add_argument("--prefix", default="turntable", help="环绕视频文件名前缀")
    ap.add_argument("--no-turntable", action="store_true", help="只渲染静帧")
    args = ap.parse_args(argv)
    if args.samples < 1:
        ap.error("--samples 必须 >= 1")
    if not args.no_turntable and args.frames < 2:
        ap.error("--frames 必须 >= 2")
    os.makedirs(args.out, exist_ok=True)
    setup_render(samples=args.samples)
    build_demo()
    render_stills(args.out)
    if not args.no_turntable:
        render_turntable(args.out, frames=args.frames, fps=args.fps,
                         prefix=args.prefix)


# Blender --python 执行时 __name__ == "__main__"；被 import 时不触发
if __name__ == "__main__":
    main()
