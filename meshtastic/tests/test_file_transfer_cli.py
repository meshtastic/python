"""Tests for meshtastic.file_transfer_cli."""

import os
import tempfile

import pytest

from meshtastic.file_transfer_cli import (
    FileTransferCliError,
    XMODEM_DEVICE_PATH_UTF8_MAX,
    check_device_paths,
    device_posix_join,
    plan_download_glob,
    plan_download_tree,
    plan_upload,
    remote_rel_glob_to_regex,
    split_remote_glob_pattern,
)


def test_device_posix_join():
    assert device_posix_join("/__ext__/d", "a/b") == "/__ext__/d/a/b"
    assert device_posix_join("/__ext__/d/", "a", "b") == "/__ext__/d/a/b"
    assert device_posix_join("/", "x") == "/x"


def test_check_device_paths():
    assert check_device_paths(["/short"]) is None
    longp = "/" + "a" * (XMODEM_DEVICE_PATH_UTF8_MAX + 1)
    assert check_device_paths([longp]) is not None


def test_plan_upload_single_plain_file():
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "one.bin")
        with open(f, "wb") as fp:
            fp.write(b"x")
        pairs = plan_upload([f], "/__ext__/out.bin")
        assert pairs == [(f, "/__ext__/out.bin")]


def test_plan_upload_glob_recursive():
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "p", "q"))
        f1 = os.path.join(d, "p", "a.txt")
        f2 = os.path.join(d, "p", "q", "b.txt")
        for fp in (f1, f2):
            with open(fp, "w") as fh:
                fh.write("x")
        pat = os.path.join(d, "p", "**", "*.txt")
        pairs = plan_upload([pat], "/__ext__/out")
        assert len(pairs) == 2
        devs = sorted(dev for _loc, dev in pairs)
        assert devs == ["/__ext__/out/a.txt", "/__ext__/out/q/b.txt"]


def test_plan_upload_directory_preserves_layout():
    with tempfile.TemporaryDirectory() as d:
        sub = os.path.join(d, "a", "b")
        os.makedirs(sub)
        f1 = os.path.join(sub, "f.txt")
        with open(f1, "w") as fp:
            fp.write("hi")
        pairs = plan_upload([d], "/__ext__/dst")
        assert len(pairs) == 1
        loc, dev = pairs[0]
        assert loc == f1
        assert dev == "/__ext__/dst/a/b/f.txt"


def test_plan_upload_dedupe():
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "x.bin")
        with open(f, "wb") as fp:
            fp.write(b"x")
        pairs = plan_upload([f, f], "/__ext__/d")
        assert len(pairs) == 1


def test_plan_upload_path_too_long():
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "x.bin")
        with open(f, "wb") as fp:
            fp.write(b"x")
        long_base = "/" + "z" * 200
        with pytest.raises(FileTransferCliError):
            plan_upload([f], long_base)


def test_split_remote_glob_pattern():
    assert split_remote_glob_pattern("/__ext__/bbs/*.md") == ("/__ext__/bbs", "*.md")
    base, rel = split_remote_glob_pattern("*.md")
    assert base == "/"
    assert rel == "*.md"


def test_remote_rel_glob_to_regex():
    rx = remote_rel_glob_to_regex("**/*.png")
    assert rx.match("a/b/c.png")
    assert rx.match("x.png")
    assert not rx.match("a/b/c.jpg")


def test_plan_download_tree():
    rows = [
        ("/__ext__/d/a.txt", 3),
        ("/__ext__/d/sub/b.bin", 2),
        ("/__ext__/d/emptydir", 0),
    ]
    with tempfile.TemporaryDirectory() as ld:
        pairs = plan_download_tree("/__ext__/d", ld, rows)
        assert len(pairs) == 2
        by = {os.path.basename(lp): dp for dp, lp in pairs}
        assert by["a.txt"] == "/__ext__/d/a.txt"
        assert by["b.bin"] == "/__ext__/d/sub/b.bin"


def test_plan_download_glob():
    rows = [
        ("/__ext__/bbs/kb/one.md", 10),
        ("/__ext__/bbs/kb/two.txt", 5),
        ("/__ext__/bbs/other/x.md", 3),
    ]
    with tempfile.TemporaryDirectory() as ld:
        pairs = plan_download_glob("/__ext__/bbs/**/*.md", ld, rows)
        assert len(pairs) == 2
        locs = sorted(lp for _dp, lp in pairs)
        assert locs[0].endswith(os.path.join("kb", "one.md"))
        assert locs[1].endswith(os.path.join("other", "x.md"))
