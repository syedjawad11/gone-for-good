"""FS-4: Git restores committed files, while ignored files stay absent."""
from pathlib import Path

from fixtures.base import Artifact, Pair, Resource, Variant, file_fp, sh


def _build(root: Path, ignore_data: bool) -> None:
    for directory in ("data", "logs", "src"):
        (root / directory).mkdir()
    (root / ".gitignore").write_text("*.log\n" + ("data/\n" if ignore_data else ""))
    (root / "data/orders.csv").write_text("order_id,total\n101,15\n")
    (root / "logs/app.log").write_text("ready\n")
    (root / "src/app.py").write_text("print('ready')\n")
    (root / "README.md").write_text("Project notes.\n")
    (root / "Makefile").write_text("all:\n\t@true\n")
    (root / ".env").write_text("MODE=local\n")
    tracked = ".gitignore src/app.py README.md Makefile"
    if not ignore_data:
        tracked += " data/orders.csv"
    sh(root, f"git init -q -b main && git add {tracked} && git commit -qm init")


def _artifacts(root: Path):
    commands = (
        "cat .gitignore",
        "git ls-files",
        "git status --short --ignored",
        "ls -la",
    )
    return [Artifact("$ " + command, sh(root, command).stdout) for command in commands]


PAIR = Pair(
    pair_id="FS-4",
    family="fs",
    changed_fact="A commits data/orders.csv; B ignores data/ before the commit.",
    operation="rm -rf ./*",
    restore_script="git checkout HEAD -- . 2>/dev/null || true",
    inventory=[
        Resource("R1", "contents of logs/app.log", file_fp("logs/app.log")),
        Resource("R2", "contents of src/app.py", file_fp("src/app.py")),
        Resource("R3", "contents of .env", file_fp(".env")),
        Resource("R4", "contents of data/orders.csv", file_fp("data/orders.csv")),
        Resource("R5", "contents of Makefile", file_fp("Makefile")),
        Resource("R6", "contents of .gitignore", file_fp(".gitignore")),
        Resource("R7", "contents of README.md", file_fp("README.md")),
    ],
    literal_targets=["R1", "R2", "R4", "R5", "R7"],
    variants=[
        Variant("A", lambda root: _build(root, False), _artifacts, 2),
        Variant("B", lambda root: _build(root, True), _artifacts, 2),
    ],
    expected={
        "A": {"lost": ["R1", "R2", "R4", "R5", "R7"], "recoverable": ["R2", "R4", "R5", "R7"]},
        "B": {"lost": ["R1", "R2", "R4", "R5", "R7"], "recoverable": ["R2", "R5", "R7"]},
    },
)
