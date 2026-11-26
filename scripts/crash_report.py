"""Echoes the output of ros2 launch and, if a node crashed, ends with its error (used by stack.py)."""
import os
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

DIED = re.compile(r"^\[ERROR\] \[(?P<node>[\w.-]+)\]: process has died \[pid \d+, exit code (?P<code>-?\d+)")
NODE_LINE = re.compile(r"^\[(?P<node>[\w.-]+)\] (?P<text>.*)$")
FILE = re.compile(r'^  File "(?P<path>[^"]+)", line (?P<line>\d+)')


def location(path: str, line: int, column: int | None = None) -> str:
    """path:line[:column], relative to the terminal's folder when inside it: Ctrl/Cmd+click opens it in VS Code."""
    cwd = os.environ.get("INIT_CWD", os.getcwd())  # pixi runs tasks from the repo root, INIT_CWD is yours
    relative = os.path.relpath(path, cwd) if os.path.splitdrive(path)[0] == os.path.splitdrive(cwd)[0] else path
    shown = path if relative.startswith("..") else relative
    return f"{shown}:{line}" + (f":{column}" if column else "")


def source_path(path: str, src: Path) -> str:
    """build/ or install/ copy of a workspace file -> the file to edit in src/."""
    parts = Path(path).parts
    for i, name in enumerate(parts[:-1]):
        candidate = src / name / name / Path(*parts[i + 1:])
        if "ros2_ws" in parts[:i] and candidate.is_file():
            return str(candidate)
    return path


class CrashReport:
    def __init__(self, src: Path):
        self._src = src
        self.stopping = False  # set on Ctrl-C: nodes dying after it did not crash
        self.crashed: tuple[str, int] | None = None
        self._lines = defaultdict(lambda: deque(maxlen=200))

    def follow(self, stream):
        for raw in stream:
            line = raw.decode("utf-8", "replace").replace("\r", "")  # Windows: \r\r\n from C++ nodes
            try:
                sys.stdout.write(line)
                sys.stdout.flush()
            except OSError:  # terminal closed: keep reading, ros2 launch must not block on a full pipe
                pass
            if "user interrupted with ctrl-c" in line:  # Windows: stack.py sees Ctrl-C only after ros2 launch
                self.stopping = True
            if (match := DIED.match(line)) is not None:
                if self.crashed is None and not self.stopping:
                    self.crashed = (match["node"], int(match["code"]))
            elif (match := NODE_LINE.match(line)) is not None:
                self._lines[match["node"]].append(match["text"].rstrip())

    def error_of(self, node: str) -> list[str]:
        """The last frame of your code in the node's last traceback, and the error itself."""
        lines = list(self._lines[node])
        starts = [i for i, text in enumerate(lines) if text.startswith("Traceback")]
        if not starts:
            return lines[-5:]
        traceback = lines[starts[-1] + 1:]
        frames = [i for i, text in enumerate(traceback) if text.startswith('  File "')]
        if not frames:
            return traceback[-3:]
        in_src = [i for i in frames if Path(source_path(FILE.match(traceback[i])["path"], self._src)).is_relative_to(self._src)]
        own = in_src or [i for i in frames if ".pixi" not in traceback[i] and "<frozen" not in traceback[i]] or frames
        start = own[-1]
        end = next((i for i in frames if i > start), len(traceback))
        tail = traceback[frames[-1] + 1:]
        error = tail[next((i for i, text in enumerate(tail) if not text.startswith(" ")), len(tail)):]
        frame = traceback[start:end] + (error if end < len(traceback) else [])
        return [FILE.sub(lambda m: "  " + location(source_path(m["path"], self._src), int(m["line"])), text) for text in frame]

    def print_summary(self) -> int:
        if self.crashed is None:
            return 0
        node, code = self.crashed
        bar = "=" * 72
        print(f"\n{bar}\n{node} crashed (exit code {code}). Its error:\n")
        print("\n".join(self.error_of(node)))
        print(f"\nFull output above.\n{bar}")
        return 1
