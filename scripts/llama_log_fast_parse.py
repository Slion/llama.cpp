#!/usr/bin/env python3
import argparse
import mmap
import re
from collections import OrderedDict
from pathlib import Path


def read_tail_text(path: Path, tail_bytes: int) -> str:
    with path.open("rb") as f:
        size = f.seek(0, 2)
        if size == 0:
            return ""
        start = max(0, size - tail_bytes)
        f.seek(start)
        data = f.read(size - start)
    return data.decode("utf-8", errors="replace")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fast parser for llama-server log interruptions")
    parser.add_argument("--log", default=r"D:\\Models\\server.log", help="Path to server.log")
    parser.add_argument("--tail-bytes", type=int, default=32 * 1024 * 1024, help="Tail window in bytes")
    parser.add_argument("--id", default="", help="Specific completion ID to inspect")
    parser.add_argument("--show-lines", type=int, default=12, help="Number of chunk lines to print")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.log)
    if not path.exists():
        print(f"error: log not found: {path}")
        return 1

    text = read_tail_text(path, args.tail_bytes)
    ids = re.findall(r"chatcmpl-[A-Za-z0-9]+", text)
    uniq = list(OrderedDict.fromkeys(ids))

    if not uniq:
        print("no completion IDs found in tail window")
        return 2

    target_id = args.id.strip() or uniq[-1]

    print(f"tail_bytes={args.tail_bytes}")
    print(f"unique_ids_in_tail={len(uniq)}")
    print("recent_ids:")
    for cid in uniq[-10:]:
        print(f"  {cid}")
    print(f"target_id={target_id}")

    lines = [
        ln for ln in text.splitlines()
        if target_id in ln and "http: streamed chunk: data:" in ln
    ]

    print(f"chunk_lines_for_target={len(lines)}")
    if not lines:
        return 0

    for ln in lines[-args.show_lines:]:
        out = ln
        if len(out) > 1500:
            out = out[:1500] + " ...[truncated]"
        print(out)

    combined = "\n".join(lines)
    has_reasoning_delta = '"reasoning_content"' in combined
    has_content_delta = '"content"' in combined
    has_tool_delta = '"tool_calls"' in combined
    has_finish_stop = '"finish_reason":"stop"' in combined
    has_finish_tools = '"finish_reason":"tool_calls"' in combined

    print("signals:")
    print(f"  reasoning_delta={has_reasoning_delta}")
    print(f"  content_delta={has_content_delta}")
    print(f"  tool_delta={has_tool_delta}")
    print(f"  finish_stop={has_finish_stop}")
    print(f"  finish_tool_calls={has_finish_tools}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
