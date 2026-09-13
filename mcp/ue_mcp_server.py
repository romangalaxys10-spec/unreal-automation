#!/usr/bin/env python3
"""Unreal Automation MCP server (stdio, JSON-RPC 2.0, zero dependencies).

Exposes headless Unreal Engine 5 tooling to any MCP client:
  ue_run_python    - run a Python script inside the UE editor session (authoring pass)
  ue_render_frames - render a LevelSequence to PNG frames via Movie Render Queue (-game)
  ue_assemble_mp4  - ffmpeg frames + audio -> h264 mp4
  ue_check_frames  - verify frame count / list output
  ue_info          - report engine/project paths

Register in your MCP client with:
  command: python3, args: [/path/to/ue_mcp_server.py]
Requires: UE 5.x install (set UE_EDITOR_CMD env or --editor arg), ffmpeg for mp4.
"""
import json
import os
import subprocess
import sys

# ---------------- configuration ----------------
UE_EDITOR_CMD = os.environ.get(
    "UE_EDITOR_CMD",
    "/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor-Cmd",
)
FFMPEG = os.environ.get(
    "UE_FFMPEG",
    "/Users/d/.zcode/workspace/default/hebrew-cyber-short/node_modules/ffmpeg-static/ffmpeg",
)
DEFAULT_PROJECT = os.environ.get(
    "UE_PROJECT", "/Users/d/.zcode/workspace/default/trump-tower-flight/UE/TrumpTowerUE.uproject"
)

TOOLS = [
    {
        "name": "ue_info",
        "description": "Report the UE editor binary, default project, and ffmpeg paths used by this server.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ue_run_python",
        "description": "Run a Python script inside a headless UE editor session (-run=pythonscript). "
        "Use for level/asset authoring (spawn actors, import textures, create materials, build sequences).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "script": {"type": "string", "description": "Absolute path to the .py script"},
                "project": {"type": "string", "description": "Optional .uproject path (defaults to UE_PROJECT)"},
                "nullrhi": {"type": "boolean", "description": "Allow -nullrhi for authoring-only passes (default true)"},
                "timeout": {"type": "integer", "description": "Seconds before abort (default 1800)"},
            },
            "required": ["script"],
        },
    },
    {
        "name": "ue_render_frames",
        "description": "Render a LevelSequence headlessly to PNG frames via Movie Render Queue runtime executor (-game mode, real GPU RHI). "
        "Requires a Content/Python executor module (e.g. TowerExecutor) + init_unreal.py in the project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sequence": {"type": "string", "description": "e.g. /Game/Seq/TowerSeq.TowerSeq"},
                "map": {"type": "string", "description": "e.g. /Game/Maps/TowerDusk"},
                "output_dir": {"type": "string", "description": "Absolute output directory for PNG frames"},
                "executor_python_class": {"type": "string", "description": "e.g. /Engine/PythonTypes.TowerExecutor"},
                "res": {"type": "array", "items": {"type": "integer"}, "description": "[w,h] window res (frames use MRQ settings)"},
                "project": {"type": "string"},
                "timeout": {"type": "integer"},
            },
            "required": ["sequence", "map", "output_dir"],
        },
    },
    {
        "name": "ue_assemble_mp4",
        "description": "Assemble PNG frames + an audio track into an h264/aac MP4 with ffmpeg (fade-in optional).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "frames_dir": {"type": "string"},
                "frames_pattern": {"type": "string", "description": "e.g. frame.%04d.png"},
                "fps": {"type": "integer"},
                "audio": {"type": "string", "description": "Audio file (wav/mp3) or empty for silent"},
                "output": {"type": "string"},
                "fade_out_start": {"type": "number"},
                "fade_out_dur": {"type": "number"},
            },
            "required": ["frames_dir", "frames_pattern", "fps", "output"],
        },
    },
    {
        "name": "ue_check_frames",
        "description": "Count PNG frames in a directory and report min/max sizes (sanity check for black/missing frames).",
        "inputSchema": {
            "type": "object",
            "properties": {"frames_dir": {"type": "string"}},
            "required": ["frames_dir"],
        },
    },
]


def run_ue(args, timeout):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        tail = "\n".join((p.stdout + p.stderr).splitlines()[-40:])
        return {"code": p.returncode, "tail": tail}
    except subprocess.TimeoutExpired:
        return {"code": -1, "tail": "TIMEOUT after %ss" % timeout}


# ---------------- tool implementations ----------------
def tool_ue_info(_):
    return {"editor": UE_EDITOR_CMD, "exists": os.path.exists(UE_EDITOR_CMD),
            "project": DEFAULT_PROJECT, "ffmpeg": FFMPEG, "ffmpeg_exists": os.path.exists(FFMPEG)}


def tool_ue_run_python(a):
    script = a["script"]
    project = a.get("project", DEFAULT_PROJECT)
    args = [UE_EDITOR_CMD, project, "-run=pythonscript", "-script=" + script,
            "-unattended", "-nopause", "-nosplash", "-stdout", "-nosound"]
    if a.get("nullrhi", True):
        args.append("-nullrhi")
    return run_ue(args, a.get("timeout", 1800))


def tool_ue_render_frames(a):
    project = a.get("project", DEFAULT_PROJECT)
    seq = a["sequence"]
    m = a["map"]
    out = a["output_dir"]
    ex = a.get("executor_python_class", "/Engine/PythonTypes.TowerExecutor")
    w, h = a.get("res", [1280, 720])
    os.makedirs(out, exist_ok=True)
    args = [UE_EDITOR_CMD, project, m, "-game",
            "-MoviePipelineLocalExecutorClass=/Script/MovieRenderPipelineCore.MoviePipelinePythonHostExecutor",
            "-ExecutorPythonClass=" + ex,
            "-LevelSequence=" + seq,
            "-OutputDir=" + out,
            "-windowed", "-resx=%d" % w, "-resy=%d" % h,
            "-stdout", "-nosound", "-nopause"]
    return run_ue(args, a.get("timeout", 7200))


def tool_ue_assemble_mp4(a):
    fd = a["frames_dir"]
    pat = a["frames_pattern"]
    fps = a.get("fps", 24)
    out = a["output"]
    if not os.path.exists(FFMPEG):
        return {"code": -1, "error": "ffmpeg not found: " + FFMPEG}
    vf = "format=yuv420p"
    if a.get("fade_out_start"):
        vf = "fade=t=out:st=%s:d=%s,%s" % (a["fade_out_start"], a.get("fade_out_dur", 1.5), vf)
    args = [FFMPEG, "-y", "-framerate", str(fps), "-i", os.path.join(fd, pat)]
    has_audio = bool(a.get("audio"))
    if has_audio:
        args += ["-i", a["audio"]]
    args += ["-filter_complex", "[0:v]" + vf + "[v]"]
    args += ["-map", "[v]"]
    if has_audio:
        args += ["-map", "1:a", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    args += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-movflags", "+faststart", out]
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=1800)
        tail = "\n".join((p.stdout + p.stderr).splitlines()[-15:])
        return {"code": p.returncode, "tail": tail, "output": out}
    except subprocess.TimeoutExpired:
        return {"code": -1, "error": "ffmpeg timeout"}


def tool_ue_check_frames(a):
    d = a["frames_dir"]
    files = sorted(f for f in os.listdir(d) if f.lower().endswith(".png")) if os.path.isdir(d) else []
    sizes = []
    for f in files:
        sizes.append(os.path.getsize(os.path.join(d, f)))
    small = [f for f, s in zip(files, sizes) if s < 20000]
    return {"count": len(files), "first": files[0] if files else None,
            "last": files[-1] if files else None,
            "suspiciously_small": len(small), "avg_kb": int(sum(sizes) / max(len(sizes), 1) // 1024)}


HANDLERS = {
    "ue_info": tool_ue_info,
    "ue_run_python": tool_ue_run_python,
    "ue_render_frames": tool_ue_render_frames,
    "ue_assemble_mp4": tool_ue_assemble_mp4,
    "ue_check_frames": tool_ue_check_frames,
}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = req.get("method", "")
        rid = req.get("id")
        if method == "initialize":
            resp = {"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "unreal-automation", "version": "1.0.0"}}}
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            resp = {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
        elif method == "tools/call":
            name = req["params"]["name"]
            args = req["params"].get("arguments") or {}
            try:
                result = {"content": [{"type": "text", "text": json.dumps(HANDLERS[name](args), indent=1)}]}
            except Exception as e:
                result = {"content": [{"type": "text", "text": "ERROR: %s" % e}], "isError": True}
            resp = {"jsonrpc": "2.0", "id": rid, "result": result}
        elif method in ("ping",):
            resp = {"jsonrpc": "2.0", "id": rid, "result": {}}
        else:
            if rid is None:
                continue
            resp = {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found: " + method}}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
