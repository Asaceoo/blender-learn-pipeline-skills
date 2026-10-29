# concept_store.py — 概念库（blender-learn-pipeline）
# Stage 1 拆解结果的沉淀与跨主题复用（对标 Math-To-Manim 反向知识树 + 语义缓存：
# 支撑层概念拆过一次，同源主题直接复用推理链，只拆增量——前置发现显著提速）。
# 存储：JSON 文件（默认 ~/.workbuddy/blender-learn-pipeline/concept-store.json），
# 不写技能目录（运行时数据与代码分离）。
import json
import time
from pathlib import Path

DEFAULT_STORE = Path.home() / ".workbuddy" / "blender-learn-pipeline" / "concept-store.json"


def _load_store(store_dir=None):
    p = Path(store_dir) if store_dir else DEFAULT_STORE
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8")), p
        except json.JSONDecodeError:
            backup = p.with_suffix(".corrupt.json")
            p.rename(backup)  # 损坏文件留档不覆盖
    return {}, p


def save_concept(topic, card, store_dir=None):
    """沉淀一个概念的 Stage 1 拆解卡。
    card 建议字段：assumptions（隐含假设）/ atomic_facts（原子事实）/
    chain（推理链步骤列表）/ layers（{core, support, extend}）/ sources。
    同名覆盖时保留 created，更新 modified。返回卡片路径。"""
    store, p = _load_store(store_dir)
    now = time.strftime("%Y-%m-%d %H:%M")
    old = store.get(topic, {})
    store[topic] = {**card, "topic": topic,
                    "created": old.get("created", now), "modified": now,
                    "reused_by": old.get("reused_by", [])}
    p.write_text(json.dumps(store, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(p)


def load_concept(topic, store_dir=None):
    """取概念卡；不存在返回 None。"""
    store, _ = _load_store(store_dir)
    return store.get(topic)


def search(keyword, store_dir=None):
    """跨概念关键词检索：命中主题名 / 原子事实 / 推理链 / 分层。返回 [(topic, 命中处)]。"""
    store, _ = _load_store(store_dir)
    k = keyword.lower()
    hits = []
    for topic, card in store.items():
        blob = json.dumps(card, ensure_ascii=False).lower()
        if k in topic.lower() or k in blob:
            hits.append(topic)
    return hits


def reuse_plan(topic, layers, store_dir=None):
    """复用规划：给新主题的支撑层概念清单，报告哪些已在库中可复用、哪些需新拆。
    layers: {"core": str, "support": [概念名...], "extend": [概念名...]}
    返回 {"reusable": [(概念, 来源主题)], "new": [概念], "hit_rate": float}"""
    store, _ = _load_store(store_dir)
    reusable, new = [], []
    for name in layers.get("support", []):
        if name in store:
            reusable.append((name, name))
        else:
            hits = search(name, store_dir)
            reusable.append((name, hits[0])) if hits else new.append(name)
    total = len(reusable) + len(new)
    hit = len(reusable) / total if total else 0.0
    # 记录复用关系（谁复用了谁）
    for name, src in reusable:
        if src in store and src != topic:
            store[src].setdefault("reused_by", [])
            if topic not in store[src]["reused_by"]:
                store[src]["reused_by"].append(topic)
    _, p = _load_store(store_dir)
    p.write_text(json.dumps(store, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"reusable": reusable, "new": new, "hit_rate": round(hit, 2)}
