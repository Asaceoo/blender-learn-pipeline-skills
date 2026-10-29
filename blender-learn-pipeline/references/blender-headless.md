# Blender 无头渲染手册（blender-headless.md）

Stage 3 的操作细节。本机实测环境：Blender 5.2，路径 `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`。

## 一、命令模板

```bash
BLENDER="C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
"$BLENDER" --background --factory-startup --python "[主题]_scene.py" -- --out "输出目录" --frames 24 --samples 48
```

- `--background`：无界面模式；`--factory-startup`：忽略用户插件与偏好，保证可复现
- `--` 之后是传给脚本的参数（`--out` 必填；`--frames` 环绕帧数默认 24；`--samples` Cycles 采样默认 48；`--no-turntable` 只出静帧）

## 二、场景脚本骨架

```python
import bpy, sys, os
# ① 把技能 scripts 目录加入 sys.path（路径按技能实际安装位置）
sys.path.insert(0, r"C:\Users\iamly\.workbuddy\skills\blender-learn-pipeline\scripts")
from blender_learn import (clear_scene, setup_world, add_light, add_box,
                           add_label, add_camera, setup_render,
                           render_stills, render_turntable)
from teaching_components import layered_tower, pipeline_flow, gear_pair, orbit_system

# ② 建主体：优先用参数化组件，一行出一个教具；无适配形态再手写 add_box/add_label
clear_scene()
setup_world()
add_light("Key", type_='SUN', energy=3.0)
layered_tower([("延伸层", (0.30, 0.55, 0.85), 3.8), ("支撑层", (0.93, 0.65, 0.15), 3.0),
               ("核心层", (0.85, 0.33, 0.25), 2.2)], title="3D 学习流水线", ring=True)

# ③ 渲染
OUT = os.path.join(os.path.dirname(bpy.data.filepath) or ".", "render")  # 或写死目录
setup_render(samples=48)
add_camera(location=(7, -7, 5), target=(0, 0, 1))
render_stills(OUT)            # 主视角/等轴/俯视 三张 PNG
render_turntable(OUT, prefix="主题—360环绕")   # 360° 环绕 mp4（交付命名用中文前缀）
```

注意：脚本里**不要**调用 `main()`——助手库的入口由 Blender 命令行触发，import 时不会执行。

## 二点五、参数化教学组件库（teaching_components.py）

| 组件 | 适用主体类型 | 关键参数 | 返回 |
|---|---|---|---|
| `layered_tower(layers, gap, title, ring)` | 层次 / 体系结构 | `layers=[(名称, 颜色, 宽度)]` 自下而上 | 对象列表 |
| `pipeline_flow(stages, seg, gap, title)` | 过程 / 流转 | `stages=[(名称, 颜色)]` 从左到右，段间自动放流向箭头 | (对象列表, 总宽度) |
| `gear_pair(teeth1, teeth2, m)` | 机制原理 | 齿数 + 模数；节圆相切、齿相位交错咬合，自动标注传动比（约分） | (对象列表, 传动比文本) |
| `orbit_system(bodies)` | 空间关系 | `bodies=[(名称, 颜色, 轨道半径, 星体半径)]`，行星自动错开角度、标签随位散布 | 对象列表 |

四组件均基于 blender_learn 原语构建（继承中文标注防重影约定），真机验证通过（齿轮咬合间距、箭头可见性、标签散布已调优）。新增组件时同样放进本模块，保持「传参数出场景」约定。

## 二点六、SolidCraft CAD 桥接（cad_bridge.py，可选）

机制原理类主体需要**精确尺寸/真实结构**（齿轮、支架、铰链、门五金件）时，用本机 SolidCraft（开源参数化 CAD，headless CLI）建模，导出 STL 后进 Blender 渲染管线：

```python
from cad_bridge import find_cli, run_cad_script, cad_snapshot, import_cad

# ① 参数化建模 + 导出（SolidCraft 单位 mm）
cmds = [{"command": "parameters.change", "params": {"name": "width", "expression": "60 mm"}},
        {"command": "sketch.create", "params": {"plane": "XZ"}},
        {"command": "sketch.line", "params": {"points": [[0,0],[40,0],[40,6],[6,6],[6,30],[0,30]], "closed": True}},
        {"command": "sketch.finish", "params": {}},
        {"command": "solid.extrude", "params": {"distance": "width", "direction": "negative", "body_name": "支架"}}]
made = run_cad_script(cmds, OUT, name="支架", formats=("stl", "step"))   # → {格式: 路径}

# ② 秒级无头快照预览（不进 Blender，确认形状再渲染）
cad_snapshot(OUT + r"\支架.sc", OUT + r"\预览.png", view="iso")

# ③ 进 Blender 渲染管线（金属灰材质 + 自动居中落地 + 中文标注/环绕）
import_cad(made["stl"], name="支架", scale=0.06)
```

实测坑（全部踩过）：
- CLI **不自动创建输出目录**（os error 3）——`run_cad_script`/`cad_snapshot` 已内置 `mkdir`
- `run --out` 不支持 glTF/glb（仅 stl/obj/step/3mf/urdf/sc；glTF 只进不出）
- STL 无材质，默认白 + 强光会**过曝成白墙**——`import_cad` 默认加金属灰材质并自动居中落地
- 对象 scale/dimensions 是惰性求值——赋值后必须 `view_layer.update()` 再读

SolidCraft 未安装时 `find_cli()` 返回 None，`run_cad_script` 抛 RuntimeError——按环境降级链处理（提示安装或退回 Blender 建模），不硬上。

## 三、中文标注（必读）

Blender 默认字体无中文字形，直接用会出豆腐块。助手库 `add_label()` 按以下顺序自动探测系统字体：

```
msyh.ttc → msyhbd.ttc → simhei.ttf → simsun.ttc → arial.ttf
```

交付前必须用看图工具**打开 PNG 亲眼确认**中文渲染正常，不能凭渲染日志判断。

## 四、渲染器选择

| 引擎 | 无头可用性 | 用途 |
|---|---|---|
| CYCLES（默认） | 稳定，纯 CPU 可跑 | 默认选择；samples 32–48，开降噪 |
| EEVEE（`BLENDER_EEVEE`） | 本机实测可用（5.2 无头出图正常）；其他机器可能因无 GPU 上下文失败 | 提速可选；失败即回退 CYCLES |

助手库 `setup_render(engine="CYCLES", samples=48, res=(1280,720))`；视图变换固定 `Standard`（默认 AgX 会把颜色洗灰）。

## 五、环绕镜头（turntable）

助手库 `render_turntable()` 的实现要点（排错用）：

- 相机挂到一个空物体（pivot）下，pivot 在目标点，Z 轴 0→2π 两关键帧线性插值，首尾帧重合 = 无缝循环
- 输出走 Blender 内置 FFMPEG（H264/MPEG4），渲染后 glob 输出目录归位为 `[前缀].mp4`
- 体积控制：24 帧 / 720p / samples 48 ≈ 数 MB；超时先降帧（24→12）

## 六、排错表（本机真机实测报错 → 处理）

| 症状 | 原因 | 处理 |
|---|---|---|
| `AttributeError: 'Action' object has no attribute 'fcurves'` | Blender 5.x 移除 `Action.fcurves`（改分层 slot：layers→strips→channelbags） | 用助手库 `_linearize()`（双版本兼容）；手写时遍历 channelbags |
| `enum "FFMPEG" not found in (...file_format...)` | Blender 5.x 视频输出改由 `image_settings.media_type` 控制 | `img.media_type='VIDEO'`（≤4.x 仍用 `file_format='FFMPEG'`），助手库已兼容 |
| 块体表面出现可读的「文字重影」 | 两个来源都会出现：①文字被粗糙镜面反射成像；②太阳光把悬空文字投影到块体上 | `add_label()` 已内置 `visible_glossy=False` + `visible_shadow=False`；自建文字务必照做 |
| 旧的 `[前缀].mp4` 残留导致新产物归位失败 | 渲染前未清理同前缀旧文件，glob 把旧文件当目标 | `render_turntable()` 已内置渲染前清理；手写时先 remove 再 render |
| `Error: Not found '--'` / argparse 报错 | 命令行漏了 `--` 分隔符 | 补上 `-- --out ...` |
| 中文全豆腐块 | 用了默认字体（无中文字形） | 确认走 `add_label()` 而非手写 FONT curve |
| EEVEE 无头黑屏 / GL 报错 | 无 GPU 上下文（个别机器） | 换 CYCLES（本机 5.2 实测 EEVEE 无头可用） |
| 渲染极慢 | samples 过高 / 分辨率过高 | samples 48→16/32，720p 保持；环绕 24 帧约 2.5 分钟（32 samples 实测） |
| 输出文件名带帧号（如 `turntable0001-0024.mp4`） | FFMPEG 动画输出命名规则 | 助手库已自动归位为单文件 |
| 颜色发灰 | 视图变换是 AgX | `scene.view_settings.view_transform = 'Standard'` |
| `blender.exe` 不在 PATH | 未加环境变量 | 用完整路径调用（见命令模板） |

## 七、限时与降级链

单件渲染 5 分钟无产物 → 降帧（24→12）→ 降采样（48→16）→ 只出 3 静帧 → 主卡注明降级。禁止无限等待，禁止交付未真实运行的伪产物。
