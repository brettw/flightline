#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
TTF_DIR = REPO_ROOT / "ttf" / "variable"
OUTPUT_ZIP = REPO_ROOT / "flightline_code.zip"
VFJ_FILES = tuple(
    REPO_ROOT / "sources" / "vfj" / f"FlightlineCode-{style}.vfj"
    for style in ("Regular", "Italic")
)
TTF_FILES = tuple(TTF_DIR / f"{source.stem}-VF.ttf" for source in VFJ_FILES)


def fail(message: str, exit_code: int = 1) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(exit_code)


def run(
    args: list[str],
    *,
    capture: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    kwargs = {
        "cwd": REPO_ROOT,
        "text": True,
    }
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE

    result = subprocess.run(args, **kwargs)
    if check and result.returncode != 0:
        if capture:
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="", file=sys.stderr)
        raise SystemExit(result.returncode)
    return result


def output(args: list[str], *, strip: bool = True) -> str:
    text = run(args, capture=True).stdout
    return text.strip() if strip else text


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        fail(f"Missing required command: {name}", 127)


def require_clean_tree() -> None:
    changes = output(["git", "status", "--porcelain", "--untracked-files=no"], strip=False)
    if changes:
        fail(f"Commit or stash tracked changes before releasing:\n{changes.rstrip()}")


def last_reachable_tag() -> str | None:
    tags = output(["git", "tag", "--merged", "HEAD", "--list", "v*.*.*"]).splitlines()
    matches = [f"--match={tag}" for tag in tags if re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag)]
    if not matches:
        return None
    return output(["git", "describe", "--tags", "--abbrev=0", *matches, "HEAD"])


def prompt_release_version(previous_tag: str | None) -> tuple[str, str]:
    print(f"Previous release: {previous_tag or 'none'}")
    print("Close FlightlineCode-Regular.vfj and FlightlineCode-Italic.vfj in FontLab.")
    try:
        version = input("After closing both files, enter the new version (major.minor.patch): ").strip()
    except EOFError:
        fail("No release version provided.")

    version = version.removeprefix("v")
    if not re.fullmatch(r"(0|[1-9][0-9]{0,4})\.(0|[1-9][0-9]?)\.[0-9]", version):
        fail("Use major.minor.patch with a minor from 0 to 99 and a patch from 0 to 9.")
    major, minor, patch = map(int, version.split("."))
    if major > 32767:
        fail("The OpenType font revision supports a major version up to 32767.")
    if previous_tag:
        previous = tuple(map(int, previous_tag[1:].split(".")))
        if (major, minor, patch) <= previous:
            fail(f"The new version must be greater than {previous_tag}.")

    # Two minor digits and one patch digit make v0.4.0 into OpenType revision 0.040.
    return f"v{version}", f"{major}.{minor:02d}{patch}"


def ensure_local_tag_missing(release_tag: str) -> None:
    result = run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/tags/{release_tag}"],
        check=False,
    )
    if result.returncode == 0:
        fail(f"Tag already exists: {release_tag}")
    if result.returncode != 1:
        raise SystemExit(result.returncode)


def ensure_remote_tag_missing(release_tag: str) -> None:
    result = run(
        [
            "git",
            "ls-remote",
            "--tags",
            "--exit-code",
            "origin",
            f"refs/tags/{release_tag}",
        ],
        capture=True,
        check=False,
    )
    if result.returncode == 0:
        fail(f"Remote tag already exists on origin: {release_tag}")
    if result.returncode != 2:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        raise SystemExit(result.returncode)


def vfj_version_fields(font_version: str) -> dict[str, int | str]:
    major, minor = map(int, font_version.split("."))
    return {"versionMajor": major, "versionMinor": minor, "version": f"Version {font_version}"}


def updated_vfj(path: Path, fields: dict[str, int | str]) -> str:
    text = path.read_bytes().decode("utf-8")
    info = json.loads(text)["font"]["info"]
    # Replace only the three scalar values. Reserializing a VFJ reformats glyph data.
    for key, value in fields.items():
        old = re.escape(json.dumps(info[key], ensure_ascii=False))
        pattern = rf'("{key}"\s*:\s*){old}(?=\s*[,}}])'
        text, count = re.subn(pattern, lambda m: m[1] + json.dumps(value), text)
        if count != 1:
            fail(f"{path.name}: expected one matching font.info.{key} field, found {count}.")
    return text


def check_ttf_version(data: bytes, font_version: str) -> None:
    # Read just the sfnt directory, head.fontRevision (16.16), and name ID 5.
    signature, num_tables = struct.unpack_from(">4sH", data)
    if signature != b"\x00\x01\x00\x00":
        raise ValueError("expected a TrueType font")
    tables = {}
    for tag, _, offset, size in struct.iter_unpack(">4sIII", data[12:12 + 16 * num_tables]):
        if offset + size > len(data):
            raise ValueError("incomplete TrueType table")
        tables[tag] = memoryview(data)[offset:offset + size]

    revision = struct.unpack_from(">i", tables[b"head"], 4)[0] / 65536
    if f"{revision:.3f}" != font_version:
        raise ValueError(f"head revision is {revision:.3f}, expected {font_version}")

    names = tables[b"name"]
    _, count, storage = struct.unpack_from(">HHH", names)
    versions = set()
    records = names[6:6 + 12 * count]
    for platform, _, _, name_id, length, offset in struct.iter_unpack(">6H", records):
        if name_id == 5:
            start = storage + offset
            encoding = "utf-16-be" if platform in (0, 3) else "ascii"
            versions.add(bytes(names[start:start + length]).decode(encoding))
    expected = f"Version {font_version}"
    if versions != {expected}:
        raise ValueError(f"name ID 5 contains {sorted(versions)}, expected {expected!r}")


def wait_for_exports(original_ttfs: dict[Path, bytes | None], font_version: str) -> None:
    print("Reopen both updated VFJs in FontLab. Use the Flightline Variable TT profile to export:")
    for path in TTF_FILES:
        print(f"  {path.relative_to(REPO_ROOT)}")
    while True:
        try:
            input("Press Enter when both TTFs have been exported (Ctrl-C to cancel): ")
        except (EOFError, KeyboardInterrupt):
            fail("\nRelease cancelled. Review the local font changes before trying again.")

        errors = []
        for path, original in original_ttfs.items():
            try:
                data = path.read_bytes()
                if data == original:
                    raise ValueError("still contains the pre-export font")
                check_ttf_version(data, font_version)
            except (OSError, ValueError, KeyError, struct.error) as error:
                errors.append(f"{path.name}: {error}")
        if not errors:
            return
        print("\n".join(errors), file=sys.stderr)
        print("Re-export the listed fonts and try again.")


@contextmanager
def atomic_output(path: Path) -> Iterator[Path]:
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, name = tempfile.mkstemp(prefix=".make_release.", suffix=path.suffix, dir=path.parent)
    os.close(fd)
    temp = Path(name)
    try:
        yield temp
        temp.chmod(mode)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def make_zip() -> None:
    with atomic_output(OUTPUT_ZIP) as temp_zip:
        with zipfile.ZipFile(
            temp_zip,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            for ttf_file in TTF_FILES:
                archive.write(ttf_file, ttf_file.name)

    print(f"Wrote {OUTPUT_ZIP.relative_to(REPO_ROOT)} with {len(TTF_FILES)} TTF files.")


def oneline_log(previous_tag: str | None) -> str:
    args = ["git", "log", "--oneline", "--decorate=no"]
    if previous_tag:
        args.append(f"{previous_tag}..HEAD")
    return output(args)


def default_commit_message(release_tag: str, previous_tag: str | None) -> str:
    return f"Release {release_tag}\n\n```\n{oneline_log(previous_tag)}\n```\n"


def write_temp_text(prefix: str, suffix: str, text: str) -> Path:
    temp_file = tempfile.NamedTemporaryFile(
        "w",
        prefix=prefix,
        suffix=suffix,
        encoding="utf-8",
        delete=False,
    )
    with temp_file:
        temp_file.write(text)
    return Path(temp_file.name)


def commit_release(release_tag: str, previous_tag: str | None) -> None:
    paths = [str(p.relative_to(REPO_ROOT)) for p in (*VFJ_FILES, *TTF_FILES, OUTPUT_ZIP)]
    run(["git", "add", "--", *paths])
    message_path = write_temp_text(
        "flightline-release-",
        ".msg",
        default_commit_message(release_tag, previous_tag),
    )
    try:
        # Ignore anything else staged while the user was exporting.
        run(["git", "commit", "--only", "--edit", "--file", str(message_path), "--", *paths])
    finally:
        if message_path.exists():
            message_path.unlink()


def current_checkout() -> tuple[str, str]:
    branch = output(["git", "branch", "--show-current"])
    if not branch:
        fail("Cannot push release commit from detached HEAD.")
    return branch, output(["git", "rev-parse", "HEAD"])


def release_notes_from_commit() -> str:
    return output(["git", "log", "-1", "--format=%b"], strip=False)


def tag_push_and_release(release_tag: str, branch: str) -> None:
    run(["git", "tag", release_tag])
    run(["git", "push", "origin", branch])
    run(["git", "push", "origin", release_tag])

    notes_path = write_temp_text(
        "flightline-release-notes-",
        ".md",
        release_notes_from_commit(),
    )
    try:
        run(
            [
                "gh",
                "release",
                "create",
                release_tag,
                str(OUTPUT_ZIP),
                "--title",
                f"Flightline Code {release_tag}",
                "--notes-file",
                str(notes_path),
                "--verify-tag",
            ]
        )
    finally:
        if notes_path.exists():
            notes_path.unlink()


def main() -> None:
    require_tool("git")
    require_clean_tree()
    require_tool("gh")
    checkout = current_checkout()

    previous_tag = last_reachable_tag()
    release_tag, font_version = prompt_release_version(previous_tag)
    ensure_local_tag_missing(release_tag)
    ensure_remote_tag_missing(release_tag)

    # Closing a FontLab window can save pending edits after the initial check.
    require_clean_tree()
    if current_checkout() != checkout:
        fail("The branch or HEAD changed while preparing the release. Start again.")
    fields = vfj_version_fields(font_version)
    sources = {path: updated_vfj(path, fields) for path in VFJ_FILES}
    original_ttfs = {path: path.read_bytes() if path.exists() else None for path in TTF_FILES}
    for path, text in sources.items():
        with atomic_output(path) as temp:
            temp.write_bytes(text.encode("utf-8"))
    print(f"Updated both VFJs to Version {font_version} for {release_tag}.")
    wait_for_exports(original_ttfs, font_version)
    if current_checkout() != checkout:
        fail("The branch or HEAD changed during export. Release stopped.")
    for path in VFJ_FILES:
        info = json.loads(path.read_bytes())["font"]["info"]
        if any(info.get(key) != value for key, value in fields.items()):
            fail(f"{path.name}: source version changed during export. Release stopped.")

    make_zip()
    commit_release(release_tag, previous_tag)
    tag_push_and_release(release_tag, checkout[0])


if __name__ == "__main__":
    main()
