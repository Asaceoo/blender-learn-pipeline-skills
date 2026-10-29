# cad_bridge.py — SolidCraft CAD 桥接（blender-learn-pipeline）
# 定位：机制原理类主体用 SolidCraft 参数化精确建模 → 导出 glTF/STL → Blender 导入走既有渲染管线
# 前提：本机装有 SolidCraft（实测 tangency-labs/solidcraft 0.25.x，headless CLI）
# 闭环：run（建模+导出）→ snapshot（秒级无头快照预览）→ import_cad（进 Blender 渲染出片）
import bpy
import json
import subprocess
from pathlib import Path

# CLI 探测候选（按序取第一个存在的）
CLI_CANDIDATES = [
    r"D:\solidcraft\SolidCraft\solidcraft-cli.exe",
    r"C:\Program Files\SolidCraft\solidcraft-cli.exe",
    r"C:\Program Files\SolidCraft\bin\solidcraft-cli.exe",
]
_cli_path = None


def find_cli():
    """探测 solidcraft-cli.exe，带缓存。找不到返回 None。"""
    global _cli_path
    if _cli_path:
        return _cli_path if Path(_cli_path).exists() else None
    import os
    for p in CLI_CANDIDATES:
        if os.path.exists(p):
            _cli_path = p
            return _cli_path
    from shutil import which
    _cli_path = which("solidcraft-cli")
    return _cli_path


def _run_cli(args, timeout=120):
    cli = find_cli()
    if not cli:
        raise RuntimeError("未找到 solidcraft-cli.exe，请在 cad_bridge.CLI_CANDIDATES 补充路径或安装 SolidCraft")
    r = subprocess.run([cli] + args, capture_output=True, text=True,
                       timeout=timeout, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"solidcraft-cli 失败({r.returncode}): {r.stdout[-400:]}\n{r.stderr[-400:]}")
    return r.stdout


def run_cad_script(commands, out_dir, name="cad_part", formats=("stl", "step"),
                   save_sc=True, timeout=300):
    """执行参数化建模脚本并导出。commands: [{command, params}] 或 script.json/sc/step 路径。
    导出格式按扩展名：glTF(.glb/.gltf)、STL、STEP、OBJ。返回 {格式: 路径}。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    args = ["run"]
    if isinstance(commands, (list, dict)):
        script = out_dir / f"{name}.script.json"
        script.write_text(json.dumps({"commands": commands} if isinstance(commands, list) else commands,
                                     ensure_ascii=False, indent=1), encoding="utf-8")
        args.append(str(script))
    else:
        args.append(str(commands))
    outs = []
    for fmt in formats:
        ext = {"stl": "stl", "step": "step", "obj": "obj", "3mf": "3mf"}[fmt]
        outs.append(str(out_dir / f"{name}.{ext}"))
    args += ["--out", *outs]
    if save_sc:
        args += ["--save", str(out_dir / f"{name}.sc")]
    _run_cli(args, timeout=timeout)
    made = {}
    for fmt, p in zip(formats, outs):
        if Path(p).exists() and Path(p).stat().st_size > 0:
            made[fmt] = p
        else:
            raise RuntimeError(f"CAD 导出缺失或为空: {p}")
    return made


def cad_snapshot(script, out_png, view="iso", width=1280, height=720, timeout=120):
    """SolidCraft 自带无头快照（秒级，预览用，不走 Blender）。view: iso/front/top/..."""
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    _run_cli(["snapshot", str(script), "--out", str(out_png), "--view", view,
              "--width", str(width), "--height", str(height)], timeout=timeout)
    if not out_png.exists() or out_png.stat().st_size == 0:
        raise RuntimeError(f"snapshot 未产出: {out_png}")
    return str(out_png)


def import_cad(path, name="CAD件", scale=0.1, color=(0.55, 0.57, 0.60), metallic=0.8,
               recenter=True):
    """把 CAD 导出体导入当前 Blender 场景（glTF/STL/OBJ 自动选导入器）。
    scale: SolidCraft 单位 mm；0.1 → 60mm 件变 6 Blender 单位。
    color/metallic: 统一 CAD 金属灰材质（STL/OBJ 无材质信息，默认白会被强光过曝成白墙）。
    recenter: 包围盒 XY 中心移到原点、底部落到 z=0，便于构图。
    返回导入的对象列表。"""
    import mathutils
    path = Path(path)
    ext = path.suffix.lower()
    before = set(bpy.data.objects)
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif ext == ".stl":
        bpy.ops.wm.stl_import(filepath=str(path))  # Blender 4.x+；旧版为 import_mesh.stl
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    else:
        raise ValueError(f"不支持的导入格式: {ext}")
    new = [o for o in set(bpy.data.objects) - before]
    mat = bpy.data.materials.new(name + "_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = 0.35
    for o in new:
        if o.parent is None:
            o.name = name
            o.scale = (scale, scale, scale)
            o.data.materials.clear()
            o.data.materials.append(mat)
    if recenter:
        bpy.context.view_layer.update()  # 尺寸/包围盒是惰性求值，不 update 拿到的是陈旧值
        for root in [o for o in new if o.parent is None]:
            corners = [root.matrix_world @ mathutils.Vector(c) for c in root.bound_box]
            mn = mathutils.Vector((min(c.x for c in corners), min(c.y for c in corners),
                                   min(c.z for c in corners)))
            mx = mathutils.Vector((max(c.x for c in corners), max(c.y for c in corners),
                                   max(c.z for c in corners)))
            center = (mn + mx) / 2
            root.location.x -= center.x
            root.location.y -= center.y
            root.location.z -= mn.z
    return new
