"""Read-only source identities and durable local evidence references."""

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_record(path):
    resolved = Path(path).expanduser().resolve(strict=True)
    require(resolved.is_file(), f"Evidence is not a file: {resolved}")
    return {"path": str(resolved), "sha256": digest(resolved.read_bytes())}


def verify_record(record):
    require(file_record(record["path"]) == record,
            f"Pinned evidence changed: {record['path']}")


def git(repo, *args):
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], stderr=subprocess.PIPE,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )


def tree_entries(repo, ref):
    entries = {}
    for row in filter(None, git(repo, "ls-tree", "-rz", ref).split(b"\0")):
        header, path = row.split(b"\t", 1)
        mode, kind, oid = header.split()
        require(kind == b"blob", "Submodules need a separate identity policy; unsupported in v1")
        entries[path] = (mode, oid)
    return entries


def checkout_attributes(attribute_repo, object_directory, ref, paths):
    names = ("text", "eol", "filter", "ident", "working-tree-encoding")
    if not paths:
        return {}
    output = subprocess.check_output(
        ["git", "--git-dir", str(attribute_repo), "-c", "core.attributesFile=/dev/null",
         "check-attr", "-z", f"--source={ref}", "--stdin", *names],
        input=b"\0".join(paths) + b"\0",
        stderr=subprocess.PIPE,
        env={**os.environ, "GIT_ATTR_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
             "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_OBJECT_DIRECTORY": object_directory,
             "GIT_OPTIONAL_LOCKS": "0"},
    )
    fields = output.split(b"\0")
    require(fields[-1] == b"" and (len(fields) - 1) % 3 == 0,
            "Cannot read committed checkout attributes")
    attributes = {path: {} for path in paths}
    for offset in range(0, len(fields) - 1, 3):
        result_path, name, value = fields[offset:offset + 3]
        require(result_path in attributes, "Checkout attribute path mismatch")
        attributes[result_path][name.decode()] = value.decode()
    require(all(set(values) == set(names) for values in attributes.values()),
            "Incomplete committed checkout attributes")
    return attributes


def checkout_conversion(attributes, path):
    inactive = {"unspecified", "unset"}
    for name in ("filter", "ident", "working-tree-encoding"):
        require(attributes[name] in inactive,
                f"Unsupported checkout attribute {name} for {os.fsdecode(path)}")
    require(attributes["eol"] in inactive | {"lf", "crlf"},
            f"Unsupported eol attribute for {os.fsdecode(path)}")
    if attributes["eol"] in inactive or attributes["eol"] == "lf" or \
            attributes["text"] == "unset":
        return None
    require(attributes["text"] in {"set", "auto", "unspecified"},
            f"Unsupported text attribute for {os.fsdecode(path)}")
    return "auto-crlf" if attributes["text"] == "auto" else "crlf"


def update_auto_crlf_stats(stats, chunk):
    for value in chunk:
        if stats["pending_cr"]:
            if value == 10:
                stats["crlf"] += 1
                stats["pending_cr"] = False
                continue
            stats["lonecr"] += 1
            stats["pending_cr"] = False
        if value == 13:
            stats["pending_cr"] = True
        elif value == 10:
            stats["lonelf"] += 1
        elif value == 127:
            stats["nonprintable"] += 1
        elif value < 32:
            if value in {8, 9, 12, 27}:
                stats["printable"] += 1
            else:
                stats["nonprintable"] += 1
                if value == 0:
                    stats["nul"] += 1
        else:
            stats["printable"] += 1
        stats["last"] = value


def hash_checkout_bytes(process, size, conversion):
    hasher = hashlib.sha256()
    converted_hasher = hashlib.sha256() if conversion == "auto-crlf" else None
    stats = ({"nul": 0, "lonecr": 0, "lonelf": 0, "crlf": 0, "printable": 0,
              "nonprintable": 0, "pending_cr": False, "last": None}
             if conversion == "auto-crlf" else None)
    pending = b""
    remaining = size
    while remaining:
        chunk = process.stdout.read(min(remaining, 1024 * 1024))
        require(bool(chunk), "Incomplete committed blob")
        remaining -= len(chunk)
        if conversion == "auto-crlf":
            hasher.update(chunk)
            update_auto_crlf_stats(stats, chunk)
            converted_hasher.update(chunk.replace(b"\n", b"\r\n"))
            continue
        if not conversion:
            hasher.update(chunk)
            continue
        chunk = pending + chunk
        pending = b""
        if remaining and chunk.endswith(b"\r"):
            chunk, pending = chunk[:-1], b"\r"
        chunk = chunk.replace(b"\r\n", b"\n")
        if conversion == "crlf":
            chunk = chunk.replace(b"\n", b"\r\n")
        hasher.update(chunk)
    hasher.update(pending)
    if conversion == "auto-crlf":
        if stats["pending_cr"]:
            stats["lonecr"] += 1
        if stats["last"] == 26:
            stats["nonprintable"] -= 1
        binary = (stats["lonecr"] or stats["nul"] or
                  stats["printable"] >> 7 < stats["nonprintable"])
        if stats["lonelf"] and not stats["crlf"] and not binary:
            return converted_hasher.hexdigest()
    return hasher.hexdigest()


def committed_snapshot(repo, baseline, ref):
    """Hash committed content as its ref-bound built-in checkout representation."""
    ref = git(repo, "rev-parse", f"{ref}^{{commit}}").decode().strip()
    baseline_paths = set(tree_entries(repo, baseline))
    entries = tree_entries(repo, ref)
    manifest = []
    object_directory = git(repo, "rev-parse", "--path-format=absolute", "--git-path",
                           "objects").decode().strip()
    with tempfile.TemporaryDirectory(prefix="feature-graph-attributes-") as temporary:
        attribute_repo = Path(temporary)
        subprocess.run(["git", "init", "--bare", "-q", str(attribute_repo)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        attribute_paths = [path for path, (mode, _) in entries.items() if mode != b"120000"]
        attributes = checkout_attributes(attribute_repo, object_directory, ref, attribute_paths)
        with subprocess.Popen(["git", "-C", str(repo), "cat-file", "--batch"],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL) as process:
            for path in sorted(baseline_paths | set(entries)):
                relative = os.fsdecode(path)
                if path not in entries:
                    manifest.append([relative, "deleted", None])
                    continue
                mode, oid = entries[path]
                process.stdin.write(oid + b"\n")
                process.stdin.flush()
                header = process.stdout.readline().split()
                require(len(header) == 3 and header[:2] == [oid, b"blob"],
                        "Cannot read committed blob")
                kind = ("symlink" if mode == b"120000" else
                        "executable" if mode == b"100755" else "file")
                conversion = None
                if kind != "symlink":
                    conversion = checkout_conversion(attributes[path], path)
                content_hash = hash_checkout_bytes(process, int(header[2]), conversion)
                require(process.stdout.read(1) == b"\n", "Invalid committed blob framing")
                manifest.append([relative, kind, content_hash])
            process.stdin.close()
            require(process.wait() == 0, "Cannot read committed source")
    return {"sha256": digest(json.dumps(manifest, ensure_ascii=True).encode()), "files": manifest}


def snapshot(repo, baseline):
    """Hash baseline/current tracked paths plus non-ignored untracked paths.

    Keep baseline deletions in the inventory so committing or signing alone
    does not change the identity. Ignored outputs are deliberately excluded.
    """
    base = git(repo, "ls-tree", "-rz", baseline).split(b"\0")
    require(not any(row.startswith(b"160000 ") for row in base),
            "Submodules need a separate identity policy; unsupported in v1")
    index = git(repo, "ls-files", "--stage", "-z").split(b"\0")
    require(not any(row.startswith(b"160000 ") for row in index),
            "Submodules need a separate identity policy; unsupported in v1")
    paths = {row.split(b"\t", 1)[1] for row in base if row}
    paths.update(filter(None, git(repo, "ls-files", "--cached", "--others",
                                  "--exclude-standard", "-z").split(b"\0")))
    manifest = []
    root = Path(repo).resolve()
    for raw in sorted(paths):
        relative = os.fsdecode(raw)
        path = root / relative
        require(path.parent.resolve().is_relative_to(root),
                f"Source parent escapes repository: {relative}")
        try:
            mode = path.lstat().st_mode
        except (FileNotFoundError, NotADirectoryError):
            manifest.append([relative, "deleted", None])
            continue
        if stat.S_ISDIR(mode):
            manifest.append([relative, "deleted", None])
            continue
        if stat.S_ISLNK(mode):
            kind, content = "symlink", os.fsencode(os.readlink(path))
        else:
            require(stat.S_ISREG(mode), f"Unsupported source entry: {relative}")
            kind = "executable" if mode & 0o111 else "file"
            content = path.read_bytes()
        manifest.append([relative, kind, digest(content)])
    identity = digest(json.dumps(manifest, ensure_ascii=True).encode())
    return {"sha256": identity, "files": manifest}
