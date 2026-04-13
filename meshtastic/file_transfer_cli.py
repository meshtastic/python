"""CLI helpers for XModem upload/download (multi-file, globs, listDir-based downloads)."""

from __future__ import annotations

import glob
import os
import posixpath
import re
from typing import Iterable, List, Optional, Sequence, Tuple

# Must match meshtastic.node.MeshInterface._XMODEM_BUFFER_MAX (path in first packet).
XMODEM_DEVICE_PATH_UTF8_MAX = 128


def device_posix_join(base: str, *parts: str) -> str:
    """Join device path segments with forward slashes; collapse duplicate slashes."""
    segs: List[str] = []
    for p in (base,) + parts:
        if not p:
            continue
        for seg in p.replace("\\", "/").split("/"):
            if seg == "" or seg == ".":
                continue
            if seg == "..":
                if segs:
                    segs.pop()
                continue
            segs.append(seg)
    return "/" + "/".join(segs) if segs else "/"


def device_path_utf8_len(path: str) -> int:
    return len(path.encode("utf-8"))


def check_device_paths(paths: Iterable[str]) -> Optional[str]:
    """Return first error message if any path exceeds XModem limit, else None."""
    for p in paths:
        n = device_path_utf8_len(p)
        if n > XMODEM_DEVICE_PATH_UTF8_MAX:
            return (
                f"Device path exceeds {XMODEM_DEVICE_PATH_UTF8_MAX} UTF-8 bytes ({n}): {p!r}"
            )
    return None


def _first_glob_magic_index(s: str) -> int:
    for i, c in enumerate(s):
        if c in "*?[":
            return i
    return -1


def _expand_local_token(token: str) -> Tuple[List[str], str]:
    """
    Expand one local CLI token to absolute file paths and a strip_prefix for relpath.

    Returns (sorted_unique_files, strip_prefix).
    """
    exp = os.path.expanduser(token)
    idx = _first_glob_magic_index(exp)

    if idx >= 0:
        raw = sorted(set(glob.glob(exp, recursive=True)))
        files = [os.path.normpath(os.path.abspath(p)) for p in raw if os.path.isfile(p)]
        if not files:
            raise FileTransferCliError(f"Glob matched no files: {token!r}")
        literal = exp[:idx]
        if not literal.strip():
            anchor = os.path.abspath(".")
        else:
            anchor = os.path.normpath(os.path.abspath(literal))
        return files, anchor

    if os.path.isfile(exp):
        p = os.path.normpath(os.path.abspath(exp))
        return [p], os.path.dirname(p)

    if os.path.isdir(exp):
        root = os.path.normpath(os.path.abspath(exp))
        out: List[str] = []
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in filenames:
                fp = os.path.join(dirpath, name)
                if os.path.isfile(fp):
                    out.append(os.path.normpath(os.path.abspath(fp)))
        return sorted(set(out)), root

    raise FileTransferCliError(f"Not a file, directory, or glob: {token!r}")


class FileTransferCliError(Exception):
    pass


def plan_upload(local_tokens: Sequence[str], remote_base: str) -> List[Tuple[str, str]]:
    """
    Build (local_abs_path, device_path) for each upload.

    Rules:
    - Exactly one local path token that is a plain file, and expansion yields one file:
      device path is ``remote_base`` as given.
    - Otherwise: device path is device_posix_join(remote_base, relpath) where relpath uses
      os.path.relpath(local_file, strip_prefix) with forward slashes.
    """
    if not local_tokens:
        raise FileTransferCliError("--upload requires at least LOCAL and REMOTE")
    remote_base = remote_base.replace("\\", "/")
    if remote_base and not remote_base.startswith("/"):
        remote_base = "/" + remote_base.lstrip("/")

    single_token_plain_file = (
        len(local_tokens) == 1
        and _first_glob_magic_index(local_tokens[0]) < 0
        and os.path.isfile(os.path.expanduser(local_tokens[0]))
    )

    entries: List[Tuple[str, str]] = []
    for tok in local_tokens:
        files, strip = _expand_local_token(tok)
        for f in files:
            entries.append((f, strip))

    if not entries:
        raise FileTransferCliError("No files to upload")

    seen: set = set()
    deduped: List[Tuple[str, str]] = []
    for f, strip in entries:
        if f in seen:
            continue
        seen.add(f)
        deduped.append((f, strip))

    use_exact_remote = len(deduped) == 1 and single_token_plain_file
    out: List[Tuple[str, str]] = []
    for local_path, strip_prefix in deduped:
        if use_exact_remote:
            dev = remote_base
        else:
            rel = os.path.relpath(local_path, strip_prefix)
            rel_posix = rel.replace(os.sep, "/")
            dev = device_posix_join(remote_base, rel_posix)
        out.append((local_path, dev))

    err = check_device_paths(dev for _loc, dev in out)
    if err:
        raise FileTransferCliError(err)
    return out


def split_remote_glob_pattern(pattern: str) -> Tuple[str, str]:
    """
    Split ``pattern`` into (list_dir_base, relative_glob) for MFLIST + filtering.

    ``list_dir_base`` is the longest leading substring with no glob metacharacters,
    normalized to a POSIX path without trailing slash (except root ``/``).
    ``relative_glob`` is the remainder (may include ``**``).
    """
    pattern = pattern.replace("\\", "/")
    idx = _first_glob_magic_index(pattern)
    if idx < 0:
        raise FileTransferCliError(
            "--download-glob pattern must contain at least one of * ? ["
        )
    if idx == 0:
        base = "/"
        rel = pattern.lstrip("/")
    else:
        literal = pattern[:idx]
        rel = pattern[idx:].lstrip("/")
        if not rel:
            raise FileTransferCliError("Invalid --download-glob pattern")
        base = posixpath.normpath(literal.rstrip("/") or "/")
        if not base.startswith("/"):
            base = "/" + base
    return base, rel


def remote_rel_glob_to_regex(rel_glob: str) -> re.Pattern[str]:
    """
    Match a path relative to list base, using ``/`` separators.
    ``**`` matches across directories; ``*`` and ``?`` do not cross ``/``.
    """
    rel_glob = rel_glob.replace("\\", "/")
    out: List[str] = ["\\A"]
    i = 0
    while i < len(rel_glob):
        if rel_glob[i : i + 2] == "**":
            if i + 2 < len(rel_glob) and rel_glob[i + 2] == "/":
                out.append("(?:.*/)?")
                i += 3
            else:
                out.append(".*")
                i += 2
        elif rel_glob[i] == "*":
            out.append("[^/]*")
            i += 1
        elif rel_glob[i] == "?":
            out.append("[^/]")
            i += 1
        elif rel_glob[i] in r".^$+{}[]|()\\":
            out.append(re.escape(rel_glob[i]))
            i += 1
        else:
            out.append(re.escape(rel_glob[i]))
            i += 1
    out.append("\\Z")
    return re.compile("".join(out))


def plan_download_tree(
    remote_dir: str, local_dir: str, rows: Sequence[Tuple[str, int]]
) -> List[Tuple[str, str]]:
    """From listDir rows, build (device_path, local_abs_path) for every file."""
    remote_dir = remote_dir.rstrip("/").replace("\\", "/")
    if not remote_dir:
        remote_dir = "/"
    if not remote_dir.startswith("/"):
        remote_dir = "/" + remote_dir

    local_root = os.path.abspath(os.path.expanduser(local_dir))
    out: List[Tuple[str, str]] = []

    for path, sz in rows:
        if sz <= 0:
            continue
        path = path.replace("\\", "/")
        if not path.startswith(remote_dir):
            continue
        tail = path[len(remote_dir) :].lstrip("/")
        if not tail:
            continue
        local_path = os.path.join(local_root, *tail.split("/"))
        out.append((path, os.path.normpath(local_path)))

    err = check_device_paths(dev for dev, _l in out)
    if err:
        raise FileTransferCliError(err)
    return out


def plan_download_glob(
    pattern: str, local_dir: str, rows: Sequence[Tuple[str, int]]
) -> List[Tuple[str, str]]:
    base, rel_pat = split_remote_glob_pattern(pattern)
    rx = remote_rel_glob_to_regex(rel_pat)
    base_n = base.rstrip("/") or "/"

    local_root = os.path.abspath(os.path.expanduser(local_dir))
    out: List[Tuple[str, str]] = []

    for path, sz in rows:
        if sz <= 0:
            continue
        path = path.replace("\\", "/")
        if base_n == "/":
            if not path.startswith("/"):
                continue
            rel = path.lstrip("/")
        else:
            if not (path == base_n or path.startswith(base_n + "/")):
                continue
            rel = path[len(base_n) :].lstrip("/")
        if not rel:
            continue
        if not rx.match(rel):
            continue
        local_path = os.path.join(local_root, *rel.split("/"))
        out.append((path, os.path.normpath(local_path)))

    err = check_device_paths(dev for dev, _l in out)
    if err:
        raise FileTransferCliError(err)
    return out
