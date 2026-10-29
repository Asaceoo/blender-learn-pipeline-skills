# web_export.py — 交互化交付（blender-learn-pipeline）
# 把当前 Blender 场景导出 GLB，并生成 model-viewer 单文件 HTML（base64 内嵌，
# 规避 glb 以 file:// 加载时的 CORS 限制——双击即可拖拽旋转，无需起服务）。
import bpy
import base64
from pathlib import Path

_VIEWER_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<script type="module" src="https://unpkg.com/@google/model-viewer@3.5.0/dist/model-viewer.min.js"></script>
<style>
  body {{ margin: 0; font-family: "Microsoft YaHei", sans-serif; background: #f2f3f5;
         display: flex; flex-direction: column; align-items: center; }}
  model-viewer {{ width: min(92vw, 900px); height: min(78vh, 640px); margin-top: 12px;
                 background: linear-gradient(#ffffff, #e8eaee); border-radius: 12px; }}
  h1 {{ font-size: 18px; color: #333; margin: 14px 0 2px; }}
  p  {{ font-size: 12px; color: #888; margin: 2px 0 10px; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p>拖拽旋转 · 滚轮缩放 · 右键平移（模型由 blender-learn-pipeline 导出）</p>
<model-viewer src="data:model/gltf-binary;base64,{b64}" camera-controls
              auto-rotate shadow-intensity="1" exposure="1"
              environment-image="neutral" interaction-prompt="auto"></model-viewer>
</body>
</html>
"""


def export_glb(out_path):
    """把当前场景导出为 GLB。返回文件路径。"""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(out_path), export_format="GLB",
                              export_apply=True)  # apply 修改器，保证几何完整
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError(f"GLB 导出失败或为空: {out_path}")
    return str(out_path)


def build_viewer_html(glb_path, out_html, title="3D 模型"):
    """GLB → model-viewer 单文件 HTML（base64 内嵌）。返回 HTML 路径。"""
    glb_path = Path(glb_path)
    if not glb_path.exists():
        raise RuntimeError(f"GLB 不存在: {glb_path}")
    b64 = base64.b64encode(glb_path.read_bytes()).decode()
    out_html = Path(out_html)
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(_VIEWER_TEMPLATE.format(title=title, b64=b64), encoding="utf-8")
    if out_html.stat().st_size < len(b64):  # HTML 至少要比 base64 大
        raise RuntimeError(f"HTML 生成异常: {out_html}")
    return str(out_html)


def export_interactive(out_dir, title="3D 模型", glb_name="模型"):
    """一步到位：当前场景 → GLB + 单文件交互 HTML。返回 (glb, html) 路径。"""
    out_dir = Path(out_dir)
    glb = export_glb(out_dir / f"{glb_name}.glb")
    html = build_viewer_html(glb, out_dir / f"{glb_name}—交互.html", title=title)
    return glb, html
