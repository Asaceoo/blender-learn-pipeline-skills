# narration.py — 音画同步（blender-learn-pipeline）
# 中文旁白合成降级链：① edge-tts CLI（在线、音质好，实测微软风控间歇 403）
#                    → ② Windows SAPI 离线语音（pywin32 COM，Huihui 中文声，稳定兜底）
# 合成后与环绕视频对齐：音频为主轴，视频不足则末帧定格延展（tpad），音频结束即收。
# 依赖：ffmpeg/ffprobe 7.x；SAPI 通道需带 pywin32 的 python（Anaconda 默认自带）。
import sys
import subprocess
from pathlib import Path

DEFAULT_VOICE = "zh-CN-YunxiNeural"  # edge-tts 年轻男声；备选 zh-CN-XiaoxiaoNeural（女）
SAPI_VOICE = "Microsoft Huihui Desktop"  # SAPI 离线中文女声
CHARS_PER_SEC = 4.0                  # 中文旁白语速预算（分镜阶段估时长用）

# SAPI 合成脚本（在带 pywin32 的解释器里执行；wav 输出路径由 argv 传入）
_SAPI_CODE = r'''
import sys, win32com.client
text, out = sys.argv[1], sys.argv[2]
v = win32com.client.Dispatch("SAPI.SpVoice")
for vv in v.GetVoices():
    if "Huihui" in vv.GetAttribute("Name"):
        v.Voice = vv; break
stream = win32com.client.Dispatch("SAPI.SpFileStream")
stream.Open(out, 3)  # SSFMCreateForWrite
v.AudioOutputStream = stream
v.Speak(text)
stream.Close()
'''

# 带 pywin32 的解释器候选（按序探测）
_PY_CANDIDATES = [sys.executable]


def _sapi_synthesize(text, out_wav):
    """Windows SAPI 离线合成（edge-tts 被风控时的兜底）。返回 wav 路径。"""
    import os
    cands = list(_PY_CANDIDATES)
    home = os.environ.get("USERPROFILE", "")
    if home:
        cands += [os.path.join(home, r"Anaconda3\python.exe"),
                  os.path.join(home, r"miniconda3\python.exe")]
    last = None
    for py in cands:
        if not (py and Path(py).exists()):
            continue
        try:
            r = subprocess.run([py, "-c", _SAPI_CODE, text, str(out_wav)],
                               capture_output=True, text=True, timeout=120,
                               encoding="utf-8", errors="replace")
            if r.returncode == 0 and Path(out_wav).exists() and Path(out_wav).stat().st_size > 1000:
                return str(out_wav)
            last = r.stderr[-200:]
        except Exception as e:
            last = str(e)[:200]
    raise RuntimeError(f"SAPI 离线合成失败（需带 pywin32 的 python）: {last}")


def _run(cmd, timeout=300):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"命令失败({r.returncode}): {' '.join(cmd[:4])}…\n{r.stderr[-400:]}")
    return r.stdout


def media_duration(path):
    """ffprobe 读媒体时长（秒，float）。"""
    out = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(path)])
    return float(out.strip().splitlines()[-1])


def estimate_duration(text):
    """按中文语速（~4 字/秒）估算旁白时长，供分镜阶段预算。"""
    return round(len(text) / CHARS_PER_SEC, 1)


def synthesize(text, out_mp3, voice=DEFAULT_VOICE, rate="+0%"):
    """文字 → 中文旁白音频。首选 edge-tts（在线），403/网络失败自动降级 SAPI 离线。
    返回 (音频路径, 时长秒, 引擎名)。"""
    if not text or not text.strip():
        raise ValueError("旁白文本为空——请先写解说词，再合成")
    out_mp3 = Path(out_mp3)
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    try:
        _run(["edge-tts", "--voice", voice, "--rate", rate,
              "--text", text, "--write-media", str(out_mp3)])
        if out_mp3.exists() and out_mp3.stat().st_size > 1000:
            return str(out_mp3), media_duration(out_mp3), "edge-tts"
    except (RuntimeError, subprocess.TimeoutExpired) as e:
        print(f"[narration] edge-tts 失败，降级 SAPI 离线语音: {str(e)[:120]}")
    wav = out_mp3.with_suffix(".sapi.wav")
    _sapi_synthesize(text, wav)
    return str(wav), media_duration(wav), "sapi-离线"


def narrate_video(video_mp4, narration_text, out_mp4, voice=DEFAULT_VOICE, rate="+0%"):
    """环绕视频 + 中文旁白 → 带声 mp4。
    视频短于旁白：末帧定格延展对齐；视频长于旁白：按音频收尾。返回 (out, 时长, 引擎)。"""
    video_mp4, out_mp4 = Path(video_mp4), Path(out_mp4)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    audio, dur, engine = synthesize(narration_text,
                                    out_mp4.parent / (out_mp4.stem + "—旁白.mp3"),
                                    voice=voice, rate=rate)
    # 视频短则末帧有限延展到音频长（stop=-1 无限流会让 -shortest 失效、ffmpeg 永不收口——实测坑），
    # 再用 -t 硬限输出时长双保险
    _run(["ffmpeg", "-y", "-i", str(video_mp4), "-i", audio,
          "-filter_complex",
          f"[0:v]tpad=stop_mode=clone:stop_duration={dur + 0.5:.2f}[v];[1:a]anull[a]",
          "-map", "[v]", "-map", "[a]", "-t", f"{dur:.2f}",
          "-c:v", "libx264", "-preset", "fast", "-crf", "20",
          "-c:a", "aac", "-b:a", "128k",
          str(out_mp4)], timeout=max(180, int(dur * 3)))
    final = media_duration(out_mp4)
    if abs(final - dur) > max(1.0, dur * 0.1):
        raise RuntimeError(f"合成时长偏差过大: 旁白 {dur:.1f}s vs 成片 {final:.1f}s")
    return str(out_mp4), final, engine
