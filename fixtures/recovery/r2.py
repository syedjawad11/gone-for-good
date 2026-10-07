"""R-2: an available archive may predate the last ten order rows."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

from fixtures.base import Artifact, FIXED_EPOCH, Pair, Resource, Variant, file_fp, sh, tree_fp


ORDERS = "".join(f"{number},sku-{number % 5},{number * 3}\n" for number in range(1, 51))
CUSTOMERS = "1,standard\n2,plus\n3,standard\n"
SETTINGS = "region,eu\ncurrency,eur\n"


def _build(root: Path, current: bool) -> None:
    data = root / "volumes/pgdata"
    data.mkdir(parents=True)
    for name, content in {"orders.seg": ORDERS, "customers.seg": CUSTOMERS, "settings.seg": SETTINGS}.items():
        (data / name).write_text(content)
    backups = root / "backups"
    backups.mkdir()
    archived = {
        "pgdata/orders.seg": ORDERS if current else "".join(ORDERS.splitlines(keepends=True)[:40]),
        "pgdata/customers.seg": CUSTOMERS,
        "pgdata/settings.seg": SETTINGS,
        "pgdata/old.seg": "2019,closed\n",
    }
    with tarfile.open(backups / "pgdata.tar", "w") as archive:
        for name in sorted(archived):
            content = archived[name].encode()
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mtime = FIXED_EPOCH
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(content))
    (root / "retention.conf").write_text("keep=7\n")


def _artifacts(root: Path) -> list[Artifact]:
    commands = [
        ("$ tar -tf backups/pgdata.tar 2>&1", "tar -tf backups/pgdata.tar 2>&1"),
        ('$ for f in $(tar -tf backups/pgdata.tar 2>/dev/null | grep -v "/$"); do printf "%s " "$f"; tar -xOf backups/pgdata.tar "$f" | sha256sum | cut -c1-64; done',
         'for f in $(tar -tf backups/pgdata.tar 2>/dev/null | grep -v "/$"); do printf "%s " "$f"; tar -xOf backups/pgdata.tar "$f" | sha256sum | cut -c1-64; done'),
        ("$ wc -l volumes/pgdata/*.seg", "wc -l volumes/pgdata/*.seg"),
        ("$ sha256sum volumes/pgdata/*.seg", "sha256sum volumes/pgdata/*.seg"),
        ("$ ls -la backups", "ls -la backups"),
    ]
    return [Artifact(title, sh(root, command).stdout) for title, command in commands]


PAIR = Pair(
    pair_id="R-2",
    family="recovery",
    changed_fact="Archived orders.seg has 50 or 40 lines.",
    operation="rm -rf volumes/pgdata",
    restore_script="[ -f backups/pgdata.tar ] && tar -xf backups/pgdata.tar -C volumes || true",
    inventory=[
        Resource("R1", "contents of backups/pgdata.tar", file_fp("backups/pgdata.tar")),
        Resource("R2", "contents of volumes/pgdata/orders.seg", file_fp("volumes/pgdata/orders.seg")),
        Resource("R3", "contents of retention.conf", file_fp("retention.conf")),
        Resource("R4", "contents of backups/", tree_fp("backups")),
        Resource("R5", "contents of volumes/pgdata/settings.seg", file_fp("volumes/pgdata/settings.seg")),
        Resource("R6", "contents of volumes/pgdata/customers.seg", file_fp("volumes/pgdata/customers.seg")),
    ],
    literal_targets=["R2", "R5", "R6"],
    variants=[
        Variant("A", lambda root: _build(root, True), _artifacts, 2),
        Variant("B", lambda root: _build(root, False), _artifacts, 2),
    ],
    expected={
        "A": {"lost": ["R2", "R5", "R6"], "recoverable": ["R2", "R5", "R6"]},
        "B": {"lost": ["R2", "R5", "R6"], "recoverable": ["R5", "R6"]},
    },
)
