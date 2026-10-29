# teaching_components.py — 参数化教学组件库（blender-learn-pipeline）
# 四个 preset：分层塔 / 管道流 / 齿轮咬合 / 轨道系统。传参数出场景，不再手写建主体。
# 依赖：同目录 blender_learn.py（sys.path 已含本目录时直接 import）
import bpy
import math
from math import radians, pi, cos, sin

from blender_learn import add_box, add_label, add_material

_DARK = (0.22, 0.22, 0.22)


def _cone_arrow(location, direction='+X', length=0.5, color=_DARK):
    """锥形指示箭头。direction: '+X' 或 '-X'。"""
    bpy.ops.mesh.primitive_cone_add(location=location)
    obj = bpy.context.active_object
    obj.name = "箭头"
    rot_y = radians(90) if direction == '+X' else radians(-90)
    obj.rotation_euler = (0, rot_y, 0)
    obj.scale = (length * 0.35, length * 0.35, length)
    obj.data.materials.append(add_material("箭头_mat", color, roughness=0.6))
    return obj


def layered_tower(layers, gap=0.05, label_size=0.45, title=None, ring=False):
    """分层塔：层次/体系结构类主体的标准件。
    layers: [(名称, (r,g,b), 宽度)]，自下而上。
    title: 顶部总标题文字（可选）；ring: 底部流程圆环（可选）。
    返回创建的对象列表。"""
    objs = []
    h = 0.9
    z = 0.0
    for name, color, w in layers:
        zc = z + h / 2
        objs.append(add_box(name, size=(w, w, h), location=(0, 0, zc), color=color))
        objs.append(add_label(name, location=(0, -w / 2 - 0.55, zc), size=label_size))
        z += h + gap
    if title:
        objs.append(add_label(title, location=(0, 0, z + 0.45), size=0.5))
    if ring:
        bpy.ops.mesh.primitive_torus_add(major_radius=max(w for _, _, w in layers) * 0.85 + 0.6,
                                         minor_radius=0.07, location=(0, 0, 0.07))
        ring_obj = bpy.context.active_object
        ring_obj.name = "流程环"
        ring_obj.data.materials.append(add_material("流程环_mat", _DARK, roughness=0.6))
        objs.append(ring_obj)
    return objs


def pipeline_flow(stages, seg=(2.2, 1.5, 1.0), gap=0.6, label_size=0.4, title=None):
    """管道流：过程/流转类主体的标准件。
    stages: [(名称, (r,g,b))]，从左到右；相邻段之间自动放流向箭头。
    返回 (对象列表, 总宽度)。"""
    objs = []
    total = len(stages) * seg[0] + (len(stages) - 1) * gap
    x = -total / 2 + seg[0] / 2
    zc = seg[2] / 2
    for i, (name, color) in enumerate(stages):
        objs.append(add_box(name, size=seg, location=(x, 0, zc), color=color))
        objs.append(add_label(name, location=(x, -seg[1] / 2 - 0.45, zc), size=label_size))
        if i < len(stages) - 1:
            objs.append(_cone_arrow((x + seg[0] / 2 + gap / 2, 0, zc), '+X', length=gap * 0.75))
        x += seg[0] + gap
    if title:
        objs.append(add_label(title, location=(0, 0, zc + seg[2] / 2 + 0.45), size=0.5))
    return objs, total


def _gear(name, teeth, m, color, center, phase=0.0, thickness=0.24):
    """单齿轮：圆柱体 + 齿（小方块沿圆周排列）。m = 模数，节径 = m × 齿数。"""
    cx, cy = center
    r = m * teeth / 2
    objs = []
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=thickness, location=(cx, cy, r))
    body = bpy.context.active_object
    body.name = name
    body.data.materials.append(add_material(name + "_mat", color, roughness=0.5))
    objs.append(body)
    for i in range(teeth):
        ang = phase + 2 * pi * i / teeth
        tr = r + m * 0.45
        bpy.ops.mesh.primitive_cube_add(
            location=(cx + tr * cos(ang), cy + tr * sin(ang), r),
            rotation=(0, 0, ang))
        tooth = bpy.context.active_object
        tooth.name = f"{name}_齿{i}"
        tooth.scale = (m * 0.55, m * 0.5, thickness * 0.45)
        tooth.data.materials.append(add_material(name + "_mat", color, roughness=0.5))
        objs.append(tooth)
    # 轴心
    bpy.ops.mesh.primitive_cylinder_add(radius=m * 0.3, depth=thickness * 1.6, location=(cx, cy, r))
    hub = bpy.context.active_object
    hub.name = name + "_轴"
    hub.data.materials.append(add_material(name + "_轴_mat", _DARK, roughness=0.4))
    objs.append(hub)
    return objs, r


def gear_pair(teeth1=12, teeth2=8, m=0.28, colors=((0.85, 0.33, 0.25), (0.30, 0.55, 0.85)),
              names=("主动轮", "从动轮"), label_size=0.38, title=None):
    """齿轮咬合：机制原理类主体的标准件。两轮节圆相切、齿相位交错咬合。
    返回 (对象列表, 传动比文本)。"""
    objs = []
    r1, r2 = m * teeth1 / 2, m * teeth2 / 2
    # 两轮节圆相切：中心距 = r1 + r2，关于原点对称
    c1 = (-(r1 + r2) / 2, 0)
    c2 = ((r1 + r2) / 2, 0)
    o1, _ = _gear(names[0], teeth1, m, colors[0], c1, phase=0.0)
    # 相位交错：从动轮转半个齿距角，齿落进主动轮的齿槽
    o2, _ = _gear(names[1], teeth2, m, colors[1], c2, phase=pi / teeth2)
    objs += o1 + o2
    objs.append(add_label(f"{names[0]} {teeth1} 齿", location=(c1[0], -r1 - 0.55, r1), size=label_size))
    objs.append(add_label(f"{names[1]} {teeth2} 齿", location=(c2[0], -r2 - 0.55, r2), size=label_size))
    from math import gcd
    g = gcd(teeth1, teeth2)
    ratio = f"传动比 {teeth1 // g}:{teeth2 // g}"
    objs.append(add_label(ratio, location=(0, -max(r1, r2) - 1.1, m * 0.2), size=0.42))
    if title:
        objs.append(add_label(title, location=(0, 0, 2 * r1 + 0.9), size=0.5))
    return objs, ratio


def orbit_system(bodies, sun_color=(0.95, 0.75, 0.25), sun_radius=0.7,
                 sun_name="中心天体", ring_color=(0.35, 0.35, 0.35), label_size=0.35):
    """轨道系统：空间关系类主体的标准件。
    bodies: [(名称, (r,g,b), 轨道半径, 星体半径)]。
    返回对象列表。"""
    objs = []
    bpy.ops.mesh.primitive_uv_sphere_add(radius=sun_radius, location=(0, 0, sun_radius))
    sun = bpy.context.active_object
    sun.name = sun_name
    sun.data.materials.append(add_material(sun_name + "_mat", sun_color, roughness=0.35))
    objs.append(sun)
    objs.append(add_label(sun_name, location=(0, -sun_radius - 0.4, sun_radius), size=label_size))
    for i, (name, color, orb_r, size) in enumerate(bodies):
        bpy.ops.mesh.primitive_torus_add(major_radius=orb_r, minor_radius=0.035,
                                         location=(0, 0, sun_radius))
        ring = bpy.context.active_object
        ring.name = name + "_轨道"
        ring.data.materials.append(add_material(ring.name + "_mat", ring_color, roughness=0.6))
        objs.append(ring)
        # 行星沿轨道错开角度分布，避免标签全部挤在同一侧
        ang = radians(30 + i * (300 / max(len(bodies), 1)))
        px, py = orb_r * cos(ang), orb_r * sin(ang)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=size, location=(px, py, sun_radius))
        planet = bpy.context.active_object
        planet.name = name
        planet.data.materials.append(add_material(name + "_mat", color, roughness=0.45))
        objs.append(planet)
        # 标签平铺在行星外侧，随角度散开
        lr = orb_r + size + 0.5
        objs.append(add_label(name, location=(lr * cos(ang), lr * sin(ang), 0.05),
                              size=label_size, vertical=False, rotation_z=ang - radians(90)))
    return objs
