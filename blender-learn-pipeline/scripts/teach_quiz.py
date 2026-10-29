# teach_quiz.py — TeachQuiz 自动评测（blender-learn-pipeline）
# Stage 5 自检闭环的结构化落地：
#   gen_quiz      按推理链生成题库（起点/推导/反例三类，写 JSON）
#   record_answer 记录作答（宿主 AI 看渲染图作答，或 ask_vlm 自动作答）
#   grade         关键词命中评分 + Markdown 报告（含缺口回流定位）
# 设计依据：Code2Video TeachQuiz——评测的目的是量化"讲没讲明白"，而非考试。
import json
from pathlib import Path

# 题目类型 → 出题指引（宿主 AI 按 pipeline-stages.md 的推理链填充）
QUIZ_KINDS = {
    "chain_start": "从推理链起点出题：考察原子事实是否真懂（不是背结论）",
    "derivation": "从中间推导出题：给出 A+B，让答者推出 C（考过程不考结果）",
    "counter_example": "边界反例题：什么情况下该概念失效/不适用",
}


def gen_quiz(topic, quiz_dir, chain_hints=None, n=5, extra=None):
    """生成题库骨架 JSON，供宿主 AI 填充题面与答案要点。
    topic: 主题名；chain_hints: [(类型, 提示)] 按推理链节点给出题方向；
    n: 题目数量，**小于三类题型数（3）时自动抬升到 3**（保证三类覆盖）。
    返回 quiz JSON 路径。"""
    n = max(int(n), len(QUIZ_KINDS))
    quiz_dir = Path(quiz_dir)
    quiz_dir.mkdir(parents=True, exist_ok=True)
    kinds = list(QUIZ_KINDS)
    items = []
    for i in range(n):
        kind = kinds[i % len(kinds)]
        hint = ""
        if chain_hints and i < len(chain_hints):
            hint = chain_hints[i]
        items.append({
            "id": f"Q{i+1}",
            "kind": kind,
            "guide": QUIZ_KINDS[kind],
            "chain_hint": hint,
            "question": "",          # 宿主 AI 填
            "answer_points": [],     # 答案要点（评分关键词来源；元素可为同义词组列表）
            "image": "",             # 对应渲染图（相对路径，可空）
            "answer": "",            # 作答（record_answer 写入）
            "score": None,           # grade 写入
        })
    quiz = {"topic": topic, "items": items}
    p = quiz_dir / f"{topic}—自检题.json"
    p.write_text(json.dumps(quiz, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(p)


def load_quiz(quiz_path):
    q = json.loads(Path(quiz_path).read_text(encoding="utf-8"))
    if not q.get("items"):
        raise ValueError(f"题库为空: {quiz_path}")
    for it in q["items"]:
        if not it.get("question") or not it.get("answer_points"):
            raise ValueError(f"{it['id']} 缺 question 或 answer_points——先由宿主 AI 填充再评测")
    return q


def record_answer(quiz_path, q_id, answer, image=None):
    """记录一道题的作答。image: 作答时实际查看的渲染图路径（复述测试留痕）。"""
    q = json.loads(Path(quiz_path).read_text(encoding="utf-8"))
    for it in q["items"]:
        if it["id"] == q_id:
            it["answer"] = answer
            if image:
                it["viewed_image"] = image
            Path(quiz_path).write_text(json.dumps(q, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
            return True
    raise ValueError(f"题目 {q_id} 不在题库中")


def grade(quiz_path, out_md=None, pass_ratio=0.6):
    """关键词命中评分：每题按 answer_points 命中比例计分，低于 pass_ratio 标记为缺口。
    返回 (报告路径或 None, 总分 0-100, 缺口题 id 列表)。"""
    q = json.loads(Path(quiz_path).read_text(encoding="utf-8"))
    lines = [f"# {q['topic']} — TeachQuiz 评测报告\n"]
    gaps, got = [], []
    for it in q["items"]:
        ans, pts = it.get("answer", ""), it.get("answer_points", [])
        if not ans:
            it["score"] = None
            lines.append(f"## {it['id']}（{it['kind']}）未作答 ⚠️\n")
            gaps.append(it["id"])
            continue
        hits = [p for p in pts if any(k in ans for k in
                ([p] if isinstance(p, str) else p))]
        ratio = len(hits) / len(pts) if pts else 1.0
        it["score"] = round(ratio * 100)
        got.append(it["score"])
        mark = "✅" if ratio >= pass_ratio else "❌ 缺口"
        if ratio < pass_ratio:
            gaps.append(it["id"])
        missing = [p for p in pts if p not in hits]
        lines.append(f"## {it['id']}（{it['kind']}）{it['score']} 分 {mark}\n")
        lines.append(f"- 命中要点：{hits or '无'}")
        if missing:
            lines.append(f"- 缺失要点：{missing} ← 回流 Stage 1/2 重讲对应环节")
        lines.append("")
    score = round(sum(got) / len(got)) if got else 0
    verdict = {k: v for k, v in
               (("set", "答案要点"), ("verdict", f"总分 {score}/100"))}
    lines.append(f"## 总评\n\n- 总分：**{score}/100**\n- 缺口题：{gaps or '无'}")
    lines.append("- 缺口回流建议：chain_start 类缺口 → 补 Stage 1 原子事实；"
                 "derivation 类缺口 → 补 Stage 2 推理链；counter_example 类缺口 → 补 Stage 4 边界")
    q["total_score"] = score
    q["gap_items"] = gaps
    src = Path(quiz_path)
    src.write_text(json.dumps(q, ensure_ascii=False, indent=1), encoding="utf-8")
    out = None
    if out_md:
        Path(out_md).parent.mkdir(parents=True, exist_ok=True)
        Path(out_md).write_text("\n".join(lines), encoding="utf-8")
        out = str(out_md)
    return out, score, gaps


def ask_vlm(image_path, question, base_url="http://127.0.0.1:8000/v1",
            model=None, timeout=30):
    """可选：调本机 OpenAI 兼容端点让 VLM 看图自动作答（如 sensetime_tray）。
    端点不可用/无视觉模型时返回 None（由宿主 AI 看图作答，不影响流程）。"""
    import urllib.request
    import base64
    try:
        req = urllib.request.Request(base_url.rstrip("/") + "/models",
                                     headers={"Authorization": "Bearer none"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            models = json.loads(r.read()).get("data", [])
    except Exception:
        return None
    vis = [m["id"] for m in models if any(k in m["id"].lower()
           for k in ("vision", "vl", "4o", "glm-4v", "qwen-vl"))]
    use = model or (vis[0] if vis else None)
    if not use:
        return None
    b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
    body = json.dumps({"model": use, "messages": [{"role": "user", "content": [
        {"type": "text", "text": question},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}],
        "max_tokens": 500}).encode()
    req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]
    except Exception:
        return None
