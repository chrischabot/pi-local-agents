#!/usr/bin/env python3
"""Capture genuine Pi model streams and their timing for the intro movie."""

from __future__ import annotations

import base64
import json
import os
import selectors
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CAPTURE_DIR = ROOT / "demo" / "captures"

SCENES = [
    {
        "slug": "qwen",
        "command": "qwen",
        "model": "Qwen 3.8 27B",
        "provider": "LOCAL · METAL",
        "thinking": "off",
        "prompt": (
            "Without using tools, introduce this repository in exactly three short, vivid "
            "sentences. It turns Qwen, Gemma, Muse Glimmer, and DeepSeek into one-command "
            "coding agents through the lightweight Pi harness; local models start on demand, "
            "while hosted models use configured APIs. Explain why that matters, and end the "
            "third sentence exactly with: One command, one capable agent."
        ),
        "prompt_display": (
            "Explain pi-agents in three vivid sentences: what it is, why Pi's lightweight "
            "harness matters, and how one-command models change the workflow."
        ),
        "accent": "#7FE7C4",
    },
    {
        "slug": "gemma",
        "command": "gemma",
        "model": "Gemma 4 12B",
        "provider": "LOCAL · METAL",
        "thinking": "off",
        "prompt": (
            "Say hello in one warm sentence. State that you are Gemma 4 12B running locally "
            "through Pi. End exactly with: Ready locally."
        ),
        "prompt_display": "Say hello, tell us your model name, and say where you're running.",
        "accent": "#F3C969",
    },
    {
        "slug": "glimmer",
        "command": "glimmer",
        "model": "Muse Glimmer 30B",
        "provider": "LOCAL · METAL",
        "thinking": "off",
        "prompt": (
            "Introduce yourself in one lively sentence: say hello, state that you are Muse "
            "Glimmer 30B running locally through Pi, and that you are built for action-heavy "
            "agent work. End exactly with: Built to act."
        ),
        "prompt_display": "Introduce yourself—and tell us what kind of agent work you love.",
        "accent": "#C39BFF",
    },
    {
        "slug": "deepseek-flash",
        "command": "deepseek-flash",
        "model": "DeepSeek V4 Flash",
        "provider": "HOSTED · API",
        "thinking": "low",
        "prompt": (
            "Create a compact, beautiful ASCII ocean wave no more than seven lines high and "
            "at most 58 characters wide. Follow it with one short goodbye line mentioning "
            "DeepSeek V4 Flash and pi-agents. Do not use a Markdown code fence. Output only "
            "the wave and goodbye line."
        ),
        "prompt_display": "Finish with a compact ASCII wave—and say goodbye.",
        "accent": "#62A8FF",
    },
]


def capture_scene(scene: dict[str, str]) -> dict:
    command = [
        scene["command"],
        "--no-session",
        "--thinking",
        scene["thinking"],
        "--no-tools",
        "--no-extensions",
        "--no-prompt-templates",
        "--no-context-files",
        "--mode",
        "json",
        "-p",
        scene["prompt"],
    ]
    env = os.environ.copy()
    env.update({"TERM": "dumb", "NO_COLOR": "1", "CLICOLOR": "0"})
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    assert process.stdout is not None and process.stderr is not None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    events: list[dict[str, object]] = []
    deadline = started + 300

    while selector.get_map():
        if time.monotonic() > deadline:
            process.terminate()
            raise TimeoutError(f"{scene['command']} exceeded five minutes")
        for key, _ in selector.select(timeout=0.25):
            chunk = os.read(key.fileobj.fileno(), 4096)
            if not chunk:
                selector.unregister(key.fileobj)
                continue
            events.append(
                {
                    "t": round(time.monotonic() - started, 4),
                    "stream": key.data,
                    "data": base64.b64encode(chunk).decode("ascii"),
                }
            )

    return_code = process.wait()
    ended = time.monotonic()
    stdout_bytes = b"".join(
        base64.b64decode(event["data"])
        for event in events
        if event["stream"] == "stdout"
    )
    stderr_bytes = b"".join(
        base64.b64decode(event["data"])
        for event in events
        if event["stream"] == "stderr"
    )
    token_events: list[dict[str, object]] = []
    pending = b""
    for event in events:
        if event["stream"] != "stdout":
            continue
        pending += base64.b64decode(event["data"])
        lines = pending.split(b"\n")
        pending = lines.pop()
        for line in lines:
            try:
                payload = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            update = payload.get("assistantMessageEvent", {})
            if update.get("type") == "text_delta" and update.get("delta"):
                token_events.append(
                    {"t": float(event["t"]), "delta": update["delta"]}
                )
    first_token = float(token_events[0]["t"]) if token_events else None
    streamed_output = "".join(str(event["delta"]) for event in token_events)
    capture = {
        "schema": 1,
        "scene": scene,
        "argv": command,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "duration": round(ended - started, 4),
        "first_token": first_token,
        "return_code": return_code,
        "token_events": token_events,
        "streamed_output": streamed_output,
    }
    if return_code != 0:
        raise RuntimeError(
            f"{scene['command']} failed ({return_code}):\n"
            f"{stderr_bytes.decode('utf-8', 'replace')[-2000:]}"
        )
    if not token_events or not streamed_output.strip():
        raise RuntimeError(f"{scene['command']} returned no streamed text deltas")
    return capture


def main() -> None:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    summary = []
    for scene in SCENES:
        print(f"Capturing {scene['command']}…", flush=True)
        capture = capture_scene(scene)
        destination = CAPTURE_DIR / f"{scene['slug']}.json"
        destination.write_text(json.dumps(capture, indent=2) + "\n")
        summary.append(
            {
                "scene": scene["slug"],
                "duration": capture["duration"],
                "first_token": capture["first_token"],
                "output": capture["streamed_output"],
            }
        )
        print(
            f"  first token at {capture['first_token']}s; done in {capture['duration']}s",
            flush=True,
        )
    (CAPTURE_DIR / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
