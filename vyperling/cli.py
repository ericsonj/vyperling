from pathlib import Path

import click

from . import __version__
from .errors import ForgeError


def _src_headers(config: dict) -> list[Path]:
    """Every *.h across the configured source dirs (the `mock --all` set)."""
    from .config import get_src_dirs

    return sorted(
        h for d in get_src_dirs(config) if d.is_dir() for h in d.rglob("*.h")
    )


def _mock_headers_for_units(config: dict, units) -> list[Path]:
    """Resolve the headers to mock from the units' `mock_<dep>.h` includes.

    Each test declares its dependency mocks via `#include "mock_<dep>.h"`. We
    find the matching `<dep>.h` in the source dirs and mock those only — never
    the unit-under-test's own source, which would collide at link time.
    """
    from .config import get_src_dirs

    src_dirs = [d for d in get_src_dirs(config) if d.is_dir()]
    deps: list[str] = []
    for unit in units:
        for dep in unit.mocks:
            if dep not in deps:
                deps.append(dep)

    headers: list[Path] = []
    for dep in deps:
        found = False
        for d in src_dirs:
            matches = sorted(d.rglob(f"{dep}.h"))
            if matches:
                headers.append(matches[0])
                found = True
                break
        if found:
            continue
    return headers


@click.group()
@click.version_option(version=__version__, prog_name="vyperling")
def cli() -> None:
    """vyperling — Embedded C test runner with cross-compilation support.

    A pip-installable replacement for Ceedling, no Ruby required.
    Run 'vyperling COMMAND --help' for help on a specific command.
    """


@cli.command()
@click.argument("name")
def new(name: str) -> None:
    """Scaffold a new vyperling project at NAME/."""
    from .scaffold import create_project

    try:
        path = create_project(name, Path.cwd())
        click.echo(f"Created vyperling project at {path}")
        click.echo(f"Next: cd {name} && vpl test")
    except ForgeError as exc:
        raise click.ClickException(str(exc)) from exc


@cli.command()
@click.option("--target", default=None,
              help="Toolchain target (defaults to targets.default in forge.yml).")
@click.option("-k", "--filter", "filter_pattern", default=None,
              help="Run only tests whose name contains PATTERN.")
@click.option("-j", "--jobs", default=1, show_default=True,
              help="Number of parallel compile jobs.")
@click.option("--coverage", is_flag=True, default=False,
              help="Enable gcov coverage (native target only).")
@click.option("--output", type=click.Choice(["junit"]), default=None,
              help="Also write test results in the given format.")
@click.option("-v", "--verbose", is_flag=True, default=False,
              help="Print every compiler command.")
@click.option("--no-mock", is_flag=True, default=False,
              help="Skip automatic mock generation.")
@click.option("--compact", is_flag=True, default=False,
              help="One line per test unit instead of per-test detail.")
@click.pass_context
def test(ctx, target, filter_pattern, jobs, coverage, output, verbose, no_mock,
         compact) -> None:
    """Discover, compile, run, and report C unit tests."""
    from .compiler import compile_all
    from .config import find_config, get_build_dir, get_mock_dir, load_config
    from .coverage import generate_coverage
    from .discoverer import discover
    from .errors import ForgeConfigError, ForgeCoverageError, ForgeToolchainError
    from .mockgen import generate_all
    from .reporter import (
        print_coverage_report,
        print_summary,
        print_terminal_report,
        write_junit_xml,
    )
    from .runner import run_all
    from .toolchains import get_toolchain

    try:
        config = load_config(find_config(Path.cwd()))
        target = target or config["targets"]["default"]
        toolchain = get_toolchain(target, config)

        cov_native = coverage and target == "native"
        if coverage and not cov_native:
            click.echo(
                f"Warning: coverage is native-only; skipping for '{target}'.",
                err=True,
            )

        units = discover(config, filter_pattern)
        if not units:
            click.echo("No tests found.")
            return

        if not no_mock:
            headers = _mock_headers_for_units(config, units)
            if headers:
                generate_all(headers, get_mock_dir(config), config, toolchain)

        results = compile_all(
            units, toolchain, config, jobs=jobs, verbose=verbose, coverage=cov_native
        )
        runs = run_all(results, toolchain)
        print_terminal_report(runs, compact=compact)
        print_summary(runs)

        if output == "junit":
            out_path = get_build_dir(config, toolchain.name) / "results.xml"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            write_junit_xml(runs, out_path)
            click.echo(f"Wrote JUnit XML to {out_path}")

        if cov_native:
            try:
                build_dir = get_build_dir(config, "native")
                index, summary = generate_coverage(config, build_dir, build_dir)
                print_coverage_report(summary)
                click.echo(f"Coverage report: {index}")
            except ForgeCoverageError as exc:
                click.echo(f"Warning: {exc}", err=True)

        failed = any(
            rr.binary is None
            or rr.timed_out
            or any((not tc.passed and not tc.ignored) for tc in rr.tests)
            for rr in runs
        )
        if failed:
            ctx.exit(1)
    except ForgeConfigError as exc:
        click.echo(f"Error: {exc}", err=True)
        ctx.exit(2)
    except ForgeToolchainError as exc:
        click.echo(f"Error: {exc}", err=True)
        ctx.exit(3)
    except ForgeError as exc:
        raise click.ClickException(str(exc)) from exc


@cli.command()
@click.option("--target", default=None,
              help="Toolchain target (defaults to targets.default in forge.yml).")
@click.option("-j", "--jobs", default=1, show_default=True,
              help="Number of parallel compile jobs.")
@click.option("-v", "--verbose", is_flag=True, default=False,
              help="Print every compiler command.")
@click.option("--no-mock", is_flag=True, default=False,
              help="Skip automatic mock generation.")
@click.pass_context
def build(ctx, target, jobs, verbose, no_mock) -> None:
    """Compile test binaries without running them."""
    from .compiler import compile_all
    from .config import find_config, get_mock_dir, load_config
    from .discoverer import discover
    from .errors import ForgeConfigError, ForgeToolchainError
    from .mockgen import generate_all
    from .toolchains import get_toolchain

    try:
        config = load_config(find_config(Path.cwd()))
        target = target or config["targets"]["default"]
        toolchain = get_toolchain(target, config)

        units = discover(config, filter_pattern=None)
        if not units:
            click.echo("No tests found.")
            return

        if not no_mock:
            headers = _mock_headers_for_units(config, units)
            if headers:
                generate_all(headers, get_mock_dir(config), config, toolchain)

        results = compile_all(
            units, toolchain, config, jobs=jobs, verbose=verbose
        )
        for r in results:
            status = "OK" if r.success else "FAIL"
            click.echo(f"[{status}] {r.unit.name}")
            if not r.success:
                click.echo(r.output, err=True)

        if any(not r.success for r in results):
            ctx.exit(1)
    except ForgeConfigError as exc:
        click.echo(f"Error: {exc}", err=True)
        ctx.exit(2)
    except ForgeToolchainError as exc:
        click.echo(f"Error: {exc}", err=True)
        ctx.exit(3)
    except ForgeError as exc:
        raise click.ClickException(str(exc)) from exc


@cli.command()
@click.argument("headers", nargs=-1)
@click.option("--all", "mock_all", is_flag=True, default=False,
              help="Mock every header in the configured source dirs.")
@click.option("--target", default="native", show_default=True,
              help="Toolchain whose preprocessor parses the headers.")
def mock(headers, mock_all, target) -> None:
    """Generate mock stubs from C header files."""
    from .config import find_config, get_mock_dir, load_config
    from .mockgen import generate_all
    from .toolchains import get_toolchain

    try:
        config = load_config(find_config(Path.cwd()))
        toolchain = get_toolchain(target, config)

        if mock_all:
            header_paths = _src_headers(config)
        else:
            header_paths = [Path(h) for h in headers]

        if not header_paths:
            click.echo("No headers to mock.")
            return

        results = generate_all(header_paths, get_mock_dir(config), config, toolchain)
        for h_path, c_path in results:
            click.echo(f"Generated {h_path} and {c_path}")
    except ForgeError as exc:
        raise click.ClickException(str(exc)) from exc


@cli.command()
@click.option("--target", default=None,
              help="Clean only the specified target's build directory.")
@click.pass_context
def clean(ctx, target) -> None:
    """Remove build artefacts."""
    import shutil

    from .config import find_config, get_build_dir, load_config
    from .errors import ForgeConfigError

    try:
        config = load_config(find_config(Path.cwd()))
        if target:
            path = get_build_dir(config, target)
        else:
            path = Path(config["project"]["build_dir"])

        if path.is_dir():
            shutil.rmtree(path)
            click.echo(f"Removed {path}")
        else:
            click.echo(f"Nothing to clean ({path} does not exist).")
    except ForgeConfigError as exc:
        click.echo(f"Error: {exc}", err=True)
        ctx.exit(2)
    except ForgeError as exc:
        raise click.ClickException(str(exc)) from exc


@cli.command()
def targets() -> None:
    """List all available toolchain profiles."""
    from .config import find_config, load_config
    from .errors import ForgeConfigError
    from .toolchains import BUILTIN_TOOLCHAINS

    try:
        config = load_config(find_config(Path.cwd()))
    except ForgeConfigError:
        config = {"toolchains": {}}

    click.echo("Built-in targets:")
    for tc in BUILTIN_TOOLCHAINS.values():
        click.echo(f"  {tc.name:<15} {tc.description}")

    click.echo()
    click.echo("Project-defined targets:")
    user = config.get("toolchains", {})
    if user:
        for name, raw in sorted(user.items()):
            click.echo(f"  {name:<15} {raw.get('description', '')}")
    else:
        click.echo("  (none)")
