"""Verify the prompt's permission sentence on every built fixture variant (run in Docker)."""
import os, stat, sys, tempfile
from pathlib import Path


from fixtures.fs import fs1,fs2,fs3,fs4,fs5,fs6,fs7,fs8,fs9,fs10
from fixtures.db import db1,db2,db3,db4,db5,db6,db7,db8,db9,db10
from fixtures.recovery import r1,r2,r3,r4,r5,r6,r7,r8,r9,r10
mods=[fs1,fs2,fs3,fs4,fs5,fs6,fs7,fs8,fs9,fs10,db1,db2,db3,db4,db5,db6,db7,db8,db9,db10,r1,r2,r3,r4,r5,r6,r7,r8,r9,r10]
uid=os.getuid(); bad=0
for m in mods:
    for v in m.PAIR.variants:
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'p'; root.mkdir(); v.build(root)
            for p in [root,*root.rglob('*')]:
                st=os.lstat(p)
                if stat.S_ISLNK(st.st_mode): continue
                rel=p.relative_to(root)
                if st.st_uid!=uid or ((stat.S_ISDIR(st.st_mode) or '.git' not in rel.parts) and not st.st_mode & stat.S_IWUSR):
                    bad+=1; print('VIOLATION', m.PAIR.pair_id, v.variant, rel, oct(st.st_mode))
print('checked', len(mods), 'pairs; violations', bad)
