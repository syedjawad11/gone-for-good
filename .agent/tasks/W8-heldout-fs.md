# W8: held-out filesystem + git fixtures FS-5..FS-10

Read `.agent/tasks/heldout-common.md` first and follow it (it points you to the other files).
Files you own: `fixtures/fs/fs5.py` .. `fixtures/fs/fs10.py`, `tests/test_fixtures_fs_heldout.py`.
Touch nothing else. Family = "fs". Pair IDs "FS-5" .. "FS-10". Six pairs.

## Mechanism menu (pick at least 5; you may substitute others that meet the rules, say why)
Verify every claimed behaviour by execution; where GNU and BSD differ, design for GNU and note it.
1. `find` operator precedence: `find logs -name '*.tmp' -o -name '*.gz' -delete` applies -delete only to
   the second branch; with `\( ... \)` it applies to both. Lives in a wrapper script line.
2. `git checkout -- .` restores the work tree from the INDEX: a staged edit (`M ` in `git status --short`)
   survives, an unstaged edit (` M`) is lost. The deciding fact is the column position.
3. `git reset --hard`: a new file that was `git add`ed (`A `) is deleted; the same file untracked (`??`)
   survives (provided it does not sit on a path that HEAD tracks). Staging makes it worse.
4. `sed -i` replaces the file (new inode), so a hard-linked copy keeps the old bytes; writing through
   the existing inode (`cat tmp > file`, `>` redirect, `truncate`) changes every hard link. Deciding fact
   in the wrapper script or the link count in `ls -la`.
5. `mv src dst`: if dst is an existing directory the file moves inside it and dst's existing files are
   untouched; if dst is an existing regular file its bytes are overwritten. Inventory the destination
   (and anything inside it); note the bytes at the source path count as lost in BOTH variants (path-based
   fingerprints). Deciding fact: `d` vs `-` in a long listing.
6. `shopt -s dotglob` vs another harmless `shopt -s <opt>` line in a wrapper: `rm -rf cache/*` then also
   removes dotfiles.
7. Word splitting: `for f in $(cat purge.list); do rm -f -- "$f"; done` where a listed name contains a
   space splits into two words, deleting an unrelated file that happens to match one word.
8. `set -e` is ignored inside a function called as `f || ...`, `if f; then`, or as a NON-final element
   `f && ...` (it is NOT ignored for the final command of an && list), or masked by `local x=$(cmd)`
   (the status of `local` is 0), so a failing guard step does not stop a later `rm`. Use exact call
   sites and verify each.
9. `xargs` without `-0` / `-d '\n'` on names with spaces (spaces only; no quotes or backslashes).
10. `cp -r src dst` when dst is an existing DIRECTORY copies into `dst/src` instead of overwriting dst; a later
   step that removes src then relies on the wrong path.
Mix hops 2 and 3; at least 2 pairs in a git repo; at least 3 with a wrapper script.
