from fixtures.base import tree_fp


def test_tree_fingerprint_separates_file_boundaries(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "a").write_bytes(b"xb\0y")
    (second / "a").write_bytes(b"x")
    (second / "b").write_bytes(b"y")
    assert tree_fp("first")(tmp_path) != tree_fp("second")(tmp_path)


def test_tree_fingerprint_includes_empty_directory(tmp_path):
    base = tmp_path / "tree"
    base.mkdir()
    fp = tree_fp("tree")
    empty = fp(tmp_path)
    assert empty is not None
    (base / "empty").mkdir()
    assert fp(tmp_path) != empty
    assert tree_fp("missing")(tmp_path) is None


def test_tree_fingerprint_includes_symlinked_directory(tmp_path):
    base = tmp_path / "tree"
    base.mkdir()
    (base / "target").mkdir()
    (base / "target" / "file").write_text("one")
    (base / "link").symlink_to("target", target_is_directory=True)
    fp = tree_fp("tree")
    with_link = fp(tmp_path)
    (base / "link").unlink()
    assert fp(tmp_path) != with_link
    (base / "link").symlink_to("elsewhere", target_is_directory=True)
    assert fp(tmp_path) != with_link
    assert tree_fp("tree/link")(tmp_path) is None
