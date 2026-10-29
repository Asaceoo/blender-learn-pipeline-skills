# cinematic.py — 电影感预设（blender-learn-pipeline）
# 去「PPT 感」三件套：轮廓光（rim）、景深虚化（DOF）、调色（exposure/gamma）。
# 一键预设：studio（默认，克制）/ dramatic（强对比）/ soft（柔光）。
# 全部基于 bpy 场景属性，headless 可用；叠加在 blender_learn 常规渲染流程之上。
import bpy
import math

_PRESETS = {
    # 白背景教学场景的电影感 = 压暗环境 + 轮廓光分离主体（正曝光会过曝成白平板——实测坑）
    "studio":   dict(rim_energy=150, exposure=-0.35, gamma=0.95, fstop=4.0, bg_strength=0.35),
    "dramatic": dict(rim_energy=300, exposure=-0.60, gamma=0.90, fstop=2.2, bg_strength=0.15),
    "soft":     dict(rim_energy=80,  exposure=-0.15, gamma=1.05, fstop=5.6, bg_strength=0.55),
}


def studio_lighting(key_loc=(4, -4, 6), fill_loc=(-5, -6, 5), rim_loc=(-3, 5, 4.5),
                    rim_energy=150, bg_strength=0.35):
    """三点光补全：常规 Key/Fill 之外加**轮廓光 rim**（从主体后上方打，勾亮边缘），
    并把世界背景压暗（bg_strength）——rim 光只在暗环境里可见。返回 rim 光对象。"""
    from blender_learn import add_light
    sc = bpy.context.scene
    if sc.world and sc.world.use_nodes:
        bg = sc.world.node_tree.nodes.get("Background")
        bg.inputs["Strength"].default_value = bg_strength
    add_light("CinKey", type_='SUN', energy=3.0, location=key_loc)
    add_light("CinFill", type_='AREA', energy=200, location=fill_loc,
              rotation=(math.radians(60), 0, math.radians(-40)))
    rim = add_light("CinRim", type_='AREA', energy=rim_energy, location=rim_loc,
                    rotation=(math.radians(-140), 0, math.radians(160)))
    return rim


def depth_of_field(camera, focus_distance=None, fstop=4.0):
    """给相机开景深虚化。focus_distance 缺省 = 相机到场景原点的距离。"""
    cam = camera.data if hasattr(camera, "data") else camera
    cam.dof.use_dof = True
    cam.dof.aperture_fstop = fstop
    if focus_distance is None:
        import mathutils
        focus_distance = camera.matrix_world.translation.length
    cam.dof.focus_distance = focus_distance
    return cam


def color_grade(exposure=0.25, gamma=0.95):
    """轻调色：Standard 变换下用 exposure + gamma 提层次（不用 AgX，避免洗灰）。"""
    sc = bpy.context.scene
    sc.view_settings.exposure = exposure
    sc.view_settings.gamma = gamma


def apply_preset(name="studio", camera=None, focus_distance=None):
    """一键电影感。name: studio/dramatic/soft。camera: 相机对象（DOF 需要）。
    返回设置摘要 dict；非法名称 ValueError。"""
    if name not in _PRESETS:
        raise ValueError(f"未知预设 {name!r}（可选：{sorted(_PRESETS)}）")
    cfg = _PRESETS[name]
    studio_lighting(rim_energy=cfg["rim_energy"])
    color_grade(exposure=cfg["exposure"], gamma=cfg["gamma"])
    used_dof = False
    if camera is not None:
        depth_of_field(camera, focus_distance=focus_distance, fstop=cfg["fstop"])
        used_dof = True
    return {"preset": name, "dof": used_dof, **cfg}
