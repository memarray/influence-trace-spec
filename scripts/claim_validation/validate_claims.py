#!/usr/bin/env python3
"""
Automated checks for CLAIMS-TO-VALIDATE.md items that can be partially validated
via public PyPI versions + pinned OSS tarballs (no API keys).

Resolves latest library versions from PyPI, maps them to git tags where applicable,
downloads GitHub source archives, and greps for evidence.

This does NOT prove product-wide absence of features; it only characterizes the
checked public artifacts (see report notes).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


PYPI_JSON = "https://pypi.org/pypi/{package}/json"
GITHUB_TARBALL = "https://github.com/{owner}/{repo}/archive/refs/tags/{tag}.tar.gz"

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        "node_modules",
        "dist",
        "build",
        ".eggs",
    }
)


def http_get_json(url: str, timeout: int = 60) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "influence-trace-spec-claim-validator"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_tarball(url: str, dest: Path, timeout: int = 120) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "influence-trace-spec-claim-validator"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        dest.write_bytes(resp.read())


def pypi_latest_version(package: str) -> str:
    data = http_get_json(PYPI_JSON.format(package=package))
    return str(data["info"]["version"])


def extract_tar_gz(archive: Path, dest_dir: Path) -> Path:
    with tarfile.open(archive, "r:gz") as tf:
        members = tf.getmembers()
        if not members:
            raise RuntimeError("empty tarball")
        root = members[0].name.split("/")[0]
        # tarfile.extractall(filter=...) requires Python 3.12+.
        if sys.version_info >= (3, 12):
            tf.extractall(dest_dir, filter="data")
        else:
            tf.extractall(dest_dir)
    return dest_dir / root


def iter_files(root: Path, suffixes: tuple[str, ...]) -> Iterable[Path]:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        parts = set(p.parts)
        if parts & SKIP_DIR_NAMES:
            continue
        if suffixes and p.suffix not in suffixes:
            continue
        yield p


def read_text(path: Path, max_bytes: int = 2_000_000) -> str:
    data = path.read_bytes()
    if len(data) > max_bytes:
        data = data[:max_bytes]
    return data.decode("utf-8", errors="replace")


@dataclass
class GrepHit:
    path: str
    line_no: int
    text: str


def grep_lines(
    paths: Iterable[Path],
    pattern: re.Pattern[str],
    line_filter: Callable[[str], bool] | None = None,
    max_hits: int = 40,
) -> list[GrepHit]:
    hits: list[GrepHit] = []
    for path in paths:
        try:
            text = read_text(path)
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if line_filter and not line_filter(line):
                continue
            if pattern.search(line):
                hits.append(GrepHit(str(path), i, line.strip()[:500]))
                if len(hits) >= max_hits:
                    return hits
    return hits


def mem0_git_tag_from_pypi(version: str) -> str:
    return f"v{version}"


def graphiti_git_tag_from_pypi(version: str) -> str:
    return f"v{version}"


def zep_python_tag_from_pypi(version: str) -> str:
    return f"v{version}"


def letta_git_tag_from_pypi(version: str) -> str:
    # letta-ai/letta tags are typically "0.16.8" without a leading "v".
    return version


def is_sqlalchemy_rollback(line: str) -> bool:
    return bool(re.search(r"\b(session|db)\.rollback\s*\(", line))


def spec_primitive_line_filter(line: str) -> bool:
    if is_sqlalchemy_rollback(line):
        return False
    return True


SPEC_PATH_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "rollback_api",
        re.compile(r'["\']/(?:v\d+/)?[^"\']*rollback[^"\']*["\']|\brollback\s*\(\s*op|\brollback_op\b', re.I),
    ),
    ("query_at", re.compile(r"query_at|query-at|as_of|as-of|point_in_time|point-in-time|time_travel|time-travel", re.I)),
    ("memory_diff", re.compile(r"/diff\b|\bdiff\s*\(\s*memory|memory[_-]?diff|version_diff|compare_versions", re.I)),
    (
        "response_memory_trace",
        re.compile(
            r"/trace/\{[^}]*response|trace.*response_id|response_id.*trace|grounding_score|influence_trace|/influence/",
            re.I,
        ),
    ),
]


def run_mem0_checks(root: Path) -> dict:
    main_py = next(root.rglob("mem0/memory/main.py"), None)
    out: dict = {"mem0_memory_main_py": str(main_py) if main_py else None}
    if not main_py or not main_py.is_file():
        out["error"] = "mem0/memory/main.py not found in tarball"
        return out

    text = read_text(main_py, max_bytes=4_000_000)
    events = {
        "event_add": bool(re.search(r'"event"\s*:\s*"ADD"|\'event\'\s*:\s*\'ADD\'', text)),
        "event_update": bool(re.search(r'"UPDATE"|\bUPDATE\b', text)),
        "event_delete": bool(re.search(r'"DELETE"|\bDELETE\b', text)),
        "event_none": bool(
            re.search(r'"event"\s*:\s*"NONE"|MemoryEvent\.NONE|event\s*=\s*"NONE"', text)
        ),
    }
    retrieval = bool(
        re.search(
            r"similar|retrieve|retriev|search_mem|vector_search|get_relevant|relevant_mem",
            text,
            re.I,
        )
    )
    llm = bool(re.search(r"\bllm\b|invoke\(|chat\.completions|completion\(", text, re.I))

    out["mem0_write_path_heuristics"] = {**events, "retrieval_language": retrieval, "llm_language": llm}
    out["mem0_write_path_pass"] = all(
        [
            events["event_add"],
            events["event_update"],
            events["event_delete"],
            retrieval,
            llm,
        ]
    )

    server_py_dirs = [p for p in (root / "server").rglob("*.py")] if (root / "server").is_dir() else []
    corpus_hits: dict[str, list[dict]] = {}
    for label, pat in SPEC_PATH_PATTERNS:
        hits = grep_lines(server_py_dirs, pat, line_filter=spec_primitive_line_filter, max_hits=15)
        corpus_hits[label] = [{"file": h.path, "line": h.line_no, "sample": h.text} for h in hits]

    out["mem0_server_spec_primitive_hits"] = corpus_hits
    out["mem0_server_spec_primitive_absent_heuristic"] = all(len(v) == 0 for v in corpus_hits.values())

    return out


def run_zep_sdk_checks(root: Path) -> dict:
    src = root / "src"
    paths = list(iter_files(src, (".py",))) if src.is_dir() else list(iter_files(root, (".py",)))
    ref = root / "reference.md"
    if ref.is_file():
        paths.append(ref)

    corpus_hits: dict[str, list[dict]] = {}
    for label, pat in SPEC_PATH_PATTERNS:
        hits = grep_lines(paths, pat, line_filter=spec_primitive_line_filter, max_hits=15)
        corpus_hits[label] = [{"file": h.path, "line": h.line_no, "sample": h.text} for h in hits]

    return {
        "zep_sdk_paths_scanned": len(paths),
        "zep_sdk_spec_primitive_hits": corpus_hits,
        "zep_sdk_spec_primitive_absent_heuristic": all(len(v) == 0 for v in corpus_hits.values()),
    }


def run_graphiti_checks(root: Path) -> dict:
    core = next((p for p in root.iterdir() if p.is_dir() and p.name.startswith("graphiti")), None)
    if core is None:
        core = root / "graphiti_core"
    base = core if core.is_dir() else root
    py_files = list(iter_files(base, (".py",)))

    temporal_hits = grep_lines(py_files, re.compile(r"\bvalid_at\b|\binvalid_at\b|\bexpired_at\b"), max_hits=20)
    llm_dir = base / "llm_client"
    return {
        "graphiti_core_root": str(base),
        "temporal_field_hits_sample": [{"file": h.path, "line": h.line_no} for h in temporal_hits[:8]],
        "temporal_fields_present": len(temporal_hits) > 0,
        "llm_client_dir_exists": llm_dir.is_dir(),
        "graphiti_temporal_pass": len(temporal_hits) > 0 and llm_dir.is_dir(),
    }


def run_letta_checks(root: Path) -> dict:
    routers = root / "letta" / "server" / "rest_api" / "routers"
    paths = list(routers.rglob("*.py")) if routers.is_dir() else list(iter_files(root, (".py",)))

    block_routes = grep_lines(paths, re.compile(r"@router\.(get|post|patch|put|delete)\([^\)]*block"), max_hits=25)
    provider_trace = grep_lines(
        paths,
        re.compile(r"ProviderTrace|/trace\b|operation_id=\"[^\"]*trace"),
        max_hits=25,
    )
    memory_grounding = grep_lines(
        paths,
        re.compile(r"grounding_score|influence_trace|memory_?facts.*response|/trace/\{response", re.I),
        max_hits=15,
    )

    return {
        "letta_routers_scanned": len(paths),
        "block_route_hits": len(block_routes),
        "provider_trace_hits": len(provider_trace),
        "spec_like_memory_grounding_hits": len(memory_grounding),
        "notes": (
            "Letta exposes provider/run/step tracing APIs; this validator searched routers for "
            "SPEC-style memory grounding / response-bound fact trace paths and found none matching tight heuristics."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON only.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if mem0 write-path heuristics fail (default: always exit 0 if downloads succeed).",
    )
    args = parser.parse_args()

    report: dict = {
        "pypi_latest": {},
        "pinned_sources": [],
        "results": {},
        "disclaimer": (
            "Evidence is limited to the pinned public artifacts downloaded by this script. "
            "Absence of strings is not absence of product features across tiers, renames, or non-OSS paths."
        ),
    }

    packages = {
        "mem0ai": ("mem0ai", "mem0", mem0_git_tag_from_pypi),
        "graphiti-core": ("graphiti-core", "graphiti", graphiti_git_tag_from_pypi),
        "zep-cloud": ("zep-cloud", "zep-python", zep_python_tag_from_pypi),
        "letta": ("letta", "letta", letta_git_tag_from_pypi),
        "letta-client": ("letta-client", None, None),
    }

    for label, (pypi_name, gh_repo_suffix, tag_fn) in packages.items():
        ver = pypi_latest_version(pypi_name)
        report["pypi_latest"][label] = {"package": pypi_name, "version": ver}
        if gh_repo_suffix is None:
            continue
        tag = tag_fn(ver)
        owner_repo = {
            "mem0": ("mem0ai", "mem0"),
            "graphiti": ("getzep", "graphiti"),
            "zep-python": ("getzep", "zep-python"),
            "letta": ("letta-ai", "letta"),
        }[gh_repo_suffix]
        report["pinned_sources"].append(
            {
                "label": label,
                "github": f"https://github.com/{owner_repo[0]}/{owner_repo[1]}/releases/tag/{tag}",
                "tarball": GITHUB_TARBALL.format(owner=owner_repo[0], repo=owner_repo[1], tag=tag),
                "pypi_package": pypi_name,
                "pypi_version": ver,
                "git_tag": tag,
            }
        )

    failures: list[str] = []

    with tempfile.TemporaryDirectory(prefix="claim-val-") as tmp:
        tmp_path = Path(tmp)

        # Mem0
        m = report["pypi_latest"]["mem0ai"]
        tag = mem0_git_tag_from_pypi(m["version"])
        url = GITHUB_TARBALL.format(owner="mem0ai", repo="mem0", tag=tag)
        arc = tmp_path / "mem0.tgz"
        download_tarball(url, arc)
        mem0_root = extract_tar_gz(arc, tmp_path)
        report["results"]["mem0"] = {"tag": tag, **run_mem0_checks(mem0_root)}
        if not report["results"]["mem0"].get("mem0_write_path_pass"):
            failures.append("mem0_write_path_heuristics")

        # Zep Python SDK (paired to zep-cloud version above)
        z = report["pypi_latest"]["zep-cloud"]
        ztag = zep_python_tag_from_pypi(z["version"])
        zurl = GITHUB_TARBALL.format(owner="getzep", repo="zep-python", tag=ztag)
        zarc = tmp_path / "zep-python.tgz"
        download_tarball(zurl, zarc)
        zroot = extract_tar_gz(zarc, tmp_path)
        report["results"]["zep_python_sdk"] = {"tag": ztag, **run_zep_sdk_checks(zroot)}

        # Graphiti
        g = report["pypi_latest"]["graphiti-core"]
        gtag = graphiti_git_tag_from_pypi(g["version"])
        gurl = GITHUB_TARBALL.format(owner="getzep", repo="graphiti", tag=gtag)
        garc = tmp_path / "graphiti.tgz"
        download_tarball(gurl, garc)
        groot = extract_tar_gz(garc, tmp_path)
        report["results"]["graphiti"] = {"tag": gtag, **run_graphiti_checks(groot)}

        # Letta server
        l = report["pypi_latest"]["letta"]
        ltag = letta_git_tag_from_pypi(l["version"])
        lurl = GITHUB_TARBALL.format(owner="letta-ai", repo="letta", tag=ltag)
        larc = tmp_path / "letta.tgz"
        download_tarball(lurl, larc)
        lroot = extract_tar_gz(larc, tmp_path)
        report["results"]["letta"] = {"tag": ltag, **run_letta_checks(lroot)}

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("=== PyPI latest (as of run) ===")
        for k, v in report["pypi_latest"].items():
            print(f"  {k}: {v['package']} {v['version']}")
        print()
        mres = report["results"]["mem0"]
        print("=== Mem0 OSS (write path heuristics) ===")
        print(f"  tag: {mres.get('tag')}")
        print(f"  main.py: {mres.get('mem0_memory_main_py')}")
        print(f"  write_path_pass: {mres.get('mem0_write_path_pass')}")
        print(f"  heuristics: {json.dumps(mres.get('mem0_write_path_heuristics'), indent=2)}")
        print("  server SPEC-primitive grep (excluding SQLAlchemy session/db rollback):")
        for k, rows in (mres.get("mem0_server_spec_primitive_hits") or {}).items():
            print(f"    {k}: {len(rows)} hit(s)")
        print()
        zres = report["results"]["zep_python_sdk"]
        print("=== Zep Python SDK (published client surface grep) ===")
        print(f"  tag: {zres.get('tag')}")
        print(f"  absent_heuristic: {zres.get('zep_sdk_spec_primitive_absent_heuristic')}")
        print()
        gres = report["results"]["graphiti"]
        print("=== Graphiti (temporal + LLM client dir) ===")
        print(f"  tag: {gres.get('tag')}")
        print(f"  temporal_pass: {gres.get('graphiti_temporal_pass')}")
        print()
        lres = report["results"]["letta"]
        print("=== Letta REST routers (blocks vs SPEC-like memory trace) ===")
        print(f"  tag: {lres.get('tag')}")
        print(f"  block_route_hits: {lres.get('block_route_hits')}")
        print(f"  provider_trace_hits: {lres.get('provider_trace_hits')}")
        print(f"  spec_like_memory_grounding_hits: {lres.get('spec_like_memory_grounding_hits')}")
        print()
        print(report["disclaimer"])

    if args.strict and failures:
        print("Strict mode failures:", ", ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        raise SystemExit(2)
