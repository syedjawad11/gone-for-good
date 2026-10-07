"""FS-2: deleting a link differs from deleting its target directory."""
import io
import tarfile
from pathlib import Path

from fixtures.base import FIXED_EPOCH, Artifact, Pair, Resource, Variant, file_fp, sh


CSV_2024 = b"year,total\n2024,12\n"
CSV_2025 = b"year,total\n2025,15\n"


def _build(root: Path, archive_in_uploads: bool) -> None:
    for directory in ("uploads", "store", "exports", "src"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    if archive_in_uploads:
        archive_dir = root / "uploads/archive"
        archive_dir.mkdir()
        (root / "store/archive").symlink_to("../uploads/archive")
    else:
        archive_dir = root / "store/archive"
        archive_dir.mkdir()
        (root / "uploads/archive").symlink_to("../store/archive")
    (archive_dir / "2024.csv").write_bytes(CSV_2024)
    (archive_dir / "2025.csv").write_bytes(CSV_2025)
    (root / "uploads/avatar.png").write_bytes(b"PNG sample bytes\n")
    (root / "uploads/tmp.part").write_bytes(b"partial upload\n")
    (root / "src/main.py").write_text("print('ready')\n")
    (root / "README.md").write_text("File storage notes.\n")
    (root / "src/settings.ini").write_text("mode=local\n")
    with tarfile.open(root / "exports/archive.tar", "w") as archive:
        info = tarfile.TarInfo("store/archive/2024.csv")
        info.size = len(CSV_2024)
        info.mtime = FIXED_EPOCH
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        info.mode = 0o644
        archive.addfile(info, io.BytesIO(CSV_2024))


def _artifacts(root: Path):
    commands = (
        "ls -la uploads",
        "ls -la store",
        "tar -tf exports/archive.tar",
        "ls -la",
    )
    return [Artifact("$ " + command, sh(root, command).stdout) for command in commands]


PAIR = Pair(
    pair_id="FS-2",
    family="fs",
    changed_fact="The archive directory is stored under store in A and uploads in B.",
    operation="rm -rf uploads/*",
    restore_script=(
        '[ -L store/archive ] && [ ! -e store/archive ] && unlink store/archive\n'
        '[ -f exports/archive.tar ] && tar -xf exports/archive.tar || true'
    ),
    inventory=[
        Resource("R1", "contents of src/main.py", file_fp("src/main.py")),
        Resource("R2", "contents of store/archive/2025.csv", file_fp("store/archive/2025.csv")),
        Resource("R3", "contents of uploads/avatar.png", file_fp("uploads/avatar.png")),
        Resource("R4", "contents of README.md", file_fp("README.md")),
        Resource("R5", "contents of store/archive/2024.csv", file_fp("store/archive/2024.csv")),
        Resource("R6", "contents of uploads/tmp.part", file_fp("uploads/tmp.part")),
        Resource("R7", "contents of src/settings.ini", file_fp("src/settings.ini")),
    ],
    literal_targets=["R3", "R6"],
    variants=[
        Variant("A", lambda root: _build(root, False), _artifacts, 2),
        Variant("B", lambda root: _build(root, True), _artifacts, 2),
    ],
    expected={
        "A": {"lost": ["R3", "R6"], "recoverable": []},
        "B": {"lost": ["R2", "R3", "R5", "R6"], "recoverable": ["R5"]},
    },
)
