#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
"""Build mdBook docs for components that provide docs/book.toml."""

from __future__ import annotations

import argparse
import logging
import os
import pathlib
import shutil
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass

logger = logging.getLogger("build_docs")


@dataclass
class BuildConfig:
    repo_root: pathlib.Path
    output_dir: pathlib.Path
    version: str = "latest"
    fail_fast: bool = True


@contextmanager
def change_directory(path: pathlib.Path):
    original = pathlib.Path.cwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original)


def _repo_name() -> str:
    return os.environ.get("GITHUB_REPOSITORY", "espressif/esp-twai-components").split(
        "/"
    )[-1]


def find_components_with_docs(repo_root: pathlib.Path) -> list[pathlib.Path]:
    """Search the repo for component folders that have docs/book.toml."""
    components: list[pathlib.Path] = []
    for book_toml in sorted(repo_root.glob("**/docs/book.toml")):
        component_dir = book_toml.parent.parent
        components.append(component_dir)
        logger.info(
            "Found component with docs: %s", component_dir.relative_to(repo_root)
        )
    return components


def run_cmd(
    cmd: list[str],
    cwd: pathlib.Path | None = None,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    if cwd is None:
        cwd = pathlib.Path.cwd()
    logger.debug("Running: %s (cwd=%s)", " ".join(cmd), cwd)
    return subprocess.run(
        cmd, cwd=str(cwd), check=check, text=True, capture_output=True, env=env
    )


def parse_doxyfile_settings(doxyfile: pathlib.Path) -> dict[str, str]:
    """Parse simple key=value settings from Doxyfile."""
    settings: dict[str, str] = {}
    for raw_line in doxyfile.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.split("#", 1)[0].strip()
        if not key:
            continue
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        settings[key] = value
    return settings


def resolve_doxygen_xml_dir(
    docs_dir: pathlib.Path, doxyfile: pathlib.Path
) -> pathlib.Path | None:
    """Resolve XML output path from Doxyfile settings."""
    settings = parse_doxyfile_settings(doxyfile)
    generate_xml = settings.get("GENERATE_XML", "YES").upper()
    if generate_xml == "NO":
        logger.warning("Doxyfile disables GENERATE_XML in %s", docs_dir)
        return None

    output_dir = settings.get("OUTPUT_DIRECTORY", "").strip()
    xml_output = settings.get("XML_OUTPUT", "xml").strip() or "xml"

    base_dir = docs_dir / output_dir if output_dir else docs_dir
    return (base_dir / xml_output).resolve()


def find_mdbook_preprocessor_commands(repo_root: pathlib.Path) -> set[str]:
    """Collect mdBook preprocessor commands referenced in docs/book.toml files."""
    commands: set[str] = set()
    for book_toml in repo_root.glob("**/docs/book.toml"):
        for raw_line in book_toml.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line.startswith("command = "):
                continue
            command = line.split("=", 1)[1].strip().strip('"').strip("'")
            if command:
                commands.add(command)
    return commands


def check_required_tools(
    repo_root: pathlib.Path, components: list[pathlib.Path]
) -> bool:
    """Ensure required external tools are available before building."""
    required_tools = {"mdbook"}
    if any((component / "docs" / "Doxyfile").exists() for component in components):
        required_tools.update({"doxygen", "esp-doxybook"})

    required_tools.update(find_mdbook_preprocessor_commands(repo_root))

    missing = [tool for tool in sorted(required_tools) if shutil.which(tool) is None]
    if missing:
        logger.error("Missing required tools: %s", ", ".join(missing))
        return False
    return True


def generate_api_docs(docs_dir: pathlib.Path) -> bool:
    """Run Doxygen and esp-doxybook to produce api.md."""
    doxyfile = docs_dir / "Doxyfile"
    if not doxyfile.exists():
        return True

    with change_directory(docs_dir):
        try:
            run_cmd(["doxygen", "Doxyfile"])
        except subprocess.CalledProcessError as e:
            logger.warning("Doxygen failed in %s: %s", docs_dir, e)
            if e.stdout:
                logger.warning(e.stdout)
            if e.stderr:
                logger.warning(e.stderr)
            return False

        xml_dir = resolve_doxygen_xml_dir(docs_dir, doxyfile)
        if xml_dir is None:
            return False

        if not xml_dir.exists():
            logger.warning("Doxygen XML output not found in %s", docs_dir)
            return False

        src_dir = docs_dir / "src"
        src_dir.mkdir(exist_ok=True)

        try:
            run_cmd(["esp-doxybook", "-i", str(xml_dir), "-o", str(src_dir / "api.md")])
        except subprocess.CalledProcessError as e:
            logger.warning("esp-doxybook failed in %s: %s", docs_dir, e)
            if e.stdout:
                logger.warning(e.stdout)
            if e.stderr:
                logger.warning(e.stderr)
            return False

    return True


def build_component_docs(component_dir: pathlib.Path, config: BuildConfig) -> bool:
    """Build mdBook documentation for a single component."""
    docs_dir = component_dir / "docs"
    rel_component = component_dir.relative_to(config.repo_root)

    logger.info("Building docs for %s", rel_component)

    if not generate_api_docs(docs_dir):
        logger.error("API doc generation failed for %s", rel_component)
        return False

    env = os.environ.copy()
    site_url = f"/{_repo_name()}/{config.version}/{rel_component.as_posix()}/"
    env["MDBOOK_OUTPUT__HTML__SITE_URL"] = site_url

    try:
        with change_directory(config.repo_root):
            result = run_cmd(["mdbook", "build", str(docs_dir)], env=env)
        if result.stdout:
            logger.debug(result.stdout)
        if result.stderr:
            logger.debug(result.stderr)
    except subprocess.CalledProcessError as e:
        logger.error("mdbook build failed for %s: %s", rel_component, e)
        if e.stdout:
            logger.error(e.stdout)
        if e.stderr:
            logger.error(e.stderr)
        return False

    source_book = docs_dir / "book"
    if not source_book.exists():
        logger.error("Missing build output: %s", source_book)
        return False

    return True


def copy_docs_to_output(component_dir: pathlib.Path, config: BuildConfig) -> bool:
    """Copy built documentation to the output directory."""
    rel_component = component_dir.relative_to(config.repo_root)
    source_book = component_dir / "docs" / "book"

    if not source_book.exists():
        logger.warning("Source path %s does not exist, skipping copy", source_book)
        return False

    dest = config.output_dir / rel_component
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_book, dest)
    logger.info("Copied %s docs to %s", rel_component, dest)
    return True


def build_all_docs(config: BuildConfig) -> bool:
    """Build documentation for all components."""
    components = find_components_with_docs(config.repo_root)
    if not components:
        logger.warning("No component docs found")
        return True

    if not check_required_tools(config.repo_root, components):
        return False

    if config.output_dir.exists():
        shutil.rmtree(config.output_dir)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    ok = True
    for component in components:
        if not build_component_docs(component, config):
            logger.error("Documentation build failed for %s", component.name)
            ok = False
            if config.fail_fast:
                logger.info("Fail-fast enabled, stopping build")
                break
        else:
            if not copy_docs_to_output(component, config):
                logger.error("Documentation copy failed for %s", component.name)
                ok = False
                if config.fail_fast:
                    logger.info("Fail-fast enabled, stopping build")
                    break

    return ok


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build component documentation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--version",
        default="latest",
        help="Version path prefix for published docs",
    )
    parser.add_argument(
        "--output-dir",
        default="docs_build_output",
        help="Directory to collect built docs",
    )
    parser.add_argument(
        "--no-fail-fast",
        action="store_true",
        help="Continue building when one component fails",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose debug output",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )

    config = BuildConfig(
        repo_root=pathlib.Path.cwd(),
        output_dir=pathlib.Path.cwd() / args.output_dir,
        version=args.version,
        fail_fast=not args.no_fail_fast,
    )

    logger.info("Building documentation with config:")
    logger.info("  Output directory: %s", config.output_dir)
    logger.info("  Version: %s", config.version)
    logger.info("  Fail fast: %s", config.fail_fast)

    success = build_all_docs(config)

    if success:
        logger.info("All documentation built successfully")
        return 0
    else:
        logger.error("Documentation build failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
