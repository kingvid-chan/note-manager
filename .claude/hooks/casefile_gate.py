#!/usr/bin/env python3
import json
import re
import sys


def deny(reason: str) -> None:
    print(f"casefile gate: {reason}", file=sys.stderr)
    raise SystemExit(2)


def main() -> None:
    data = json.load(sys.stdin)
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    if tool in {"Edit", "Write", "MultiEdit", "NotebookEdit"}:
        path = str(tool_input.get("file_path", "")).replace("\\", "/")
        if (
            path == "case"
            or path.startswith("case/")
            or "/case/" in path
            or path.endswith("/case")
        ):
            deny("case/ 只能由 Hermes 的 casefile 工具修改")
    if tool == "Bash":
        command = str(tool_input.get("command", ""))
        normalized = " ".join(command.split())
        if re.search(
            r"(?:>>?|tee\s+(?:-a\s+)?|sed\s+-i\S*)[^;&|]*case/",
            normalized,
        ):
            deny("禁止通过 shell 修改 case/")
        if re.search(r"\bcasefile\.py\b", normalized):
            deny("casefile 工具只允许 Hermes 调用")
        broad_add = re.search(
            r"\bgit\s+add\s+(?:-A|--all)(?:\s|$)|"
            r"\bgit\s+add\s+\.(?:\s|$)|"
            r"\bgit\s+add\b[^;&|]*\bcase/",
            normalized,
        )
        commit_all = re.search(
            r"\bgit\s+commit\b[^;&|]*(?:"
            r"\s-[A-Za-z]*a[A-Za-z]*(?:\s|$)|"
            r"\s--all(?:\s|$))",
            normalized,
        )
        if broad_add or commit_all:
            deny("技术专家必须精确暂存代码文件，避免带入 Hermes 案卷变更")
        if re.search(r"\bgit\b[^;&|]*\b(?:merge|tag|push)\b", normalized):
            deny("技术专家不得合并、打 tag 或 push 发布")
        if re.search(
            r"\bssh\s+aliyun-cowork\b|\bsystemctl\b|\bnginx\b",
            normalized,
        ):
            deny("技术专家不得执行交付部署")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
