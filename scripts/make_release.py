#!/usr/bin/env python3

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
TTF_DIR = REPO_ROOT / "ttf" / "variable"
OUTPUT_ZIP = REPO_ROOT / "flightline_code.zip"


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


def last_reachable_tag() -> str | None:
    result = run(
        ["git", "describe", "--tags", "--abbrev=0", "HEAD"],
        capture=True,
        check=False,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def prompt_release_tag(previous_tag: str | None) -> str:
    previous_label = previous_tag or "none"
    try:
        release_tag = input(
            f"Previous tag was “{previous_label}”, enter new release tag: "
        ).strip()
    except EOFError:
        fail("No release tag provided.")

    if not release_tag:
        fail("No release tag provided.")

    result = run(
        ["git", "check-ref-format", f"refs/tags/{release_tag}"],
        capture=True,
        check=False,
    )
    if result.returncode != 0:
        fail(f"Invalid release tag: {release_tag}")

    result = run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/tags/{release_tag}"],
        check=False,
    )
    if result.returncode == 0:
        fail(f"Tag already exists: {release_tag}")
    if result.returncode != 1:
        raise SystemExit(result.returncode)

    return release_tag


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


def make_zip() -> None:
    if not TTF_DIR.is_dir():
        fail(f"Missing TTF directory: {TTF_DIR}")

    ttf_files = sorted(TTF_DIR.glob("*.ttf"))
    if not ttf_files:
        fail(f"No .ttf files found in {TTF_DIR}")

    output_mode = OUTPUT_ZIP.stat().st_mode & 0o777 if OUTPUT_ZIP.exists() else 0o644
    temp_fd, temp_name = tempfile.mkstemp(
        prefix=".make_release.",
        suffix=".zip",
        dir=REPO_ROOT,
    )
    os.close(temp_fd)
    temp_zip = Path(temp_name)

    try:
        with zipfile.ZipFile(
            temp_zip,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            for ttf_file in ttf_files:
                archive.write(ttf_file, ttf_file.name)

        temp_zip.chmod(output_mode)
        temp_zip.replace(OUTPUT_ZIP)
    except Exception:
        if temp_zip.exists():
            temp_zip.unlink()
        raise

    print(f"Wrote {OUTPUT_ZIP.relative_to(REPO_ROOT)} with {len(ttf_files)} TTF files.")


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
    run(["git", "add", str(OUTPUT_ZIP.relative_to(REPO_ROOT))])

    message_path = write_temp_text(
        "flightline-release-",
        ".msg",
        default_commit_message(release_tag, previous_tag),
    )
    try:
        # The release ZIP may already be committed; still record release notes.
        run(["git", "commit", "--allow-empty", "--edit", "--file", str(message_path)])
    finally:
        if message_path.exists():
            message_path.unlink()


def current_branch() -> str:
    branch = output(["git", "branch", "--show-current"])
    if not branch:
        fail("Cannot push release commit from detached HEAD.")
    return branch


def release_notes_from_commit() -> str:
    return output(["git", "log", "-1", "--format=%b"], strip=False)


def tag_push_and_release(release_tag: str) -> None:
    branch = current_branch()

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
    require_tool("gh")

    previous_tag = last_reachable_tag()
    release_tag = prompt_release_tag(previous_tag)
    current_branch()
    ensure_remote_tag_missing(release_tag)

    make_zip()
    commit_release(release_tag, previous_tag)
    tag_push_and_release(release_tag)


if __name__ == "__main__":
    main()
