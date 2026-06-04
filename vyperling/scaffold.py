"""vyperling.scaffold — `vpl new` project skeleton generator.

Renders a working project skeleton (forge.yml, a trivial src module, a passing
Unity test, an empty mocks dir, and a README) from jinja2 templates bundled in
``vyperling/templates/``. The generated ``test_example.c`` compiles and passes on
the first ``vpl test`` with native gcc, verifying the toolchain end-to-end.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, PackageLoader, StrictUndefined

from vyperling.errors import ForgeScaffoldError

# (relative output path, template name) — rendered with {"name": <project>}.
_TEMPLATES: list[tuple[str, str]] = [
    ("forge.yml", "scaffold_forge_yml.j2"),
    ("README.md", "scaffold_readme_md.j2"),
    ("src/example.h", "scaffold_example_h.j2"),
    ("src/example.c", "scaffold_example_c.j2"),
    ("test/test_example.c", "scaffold_test_example_c.j2"),
]

_env: Environment | None = None


def _environment() -> Environment:
    """Lazy singleton jinja2 env — mirrors mockgen._environment configuration."""
    global _env
    if _env is None:
        _env = Environment(
            loader=PackageLoader("vyperling", "templates"),
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=StrictUndefined,
            keep_trailing_newline=True,
        )
    return _env


def create_project(name: str, base_dir: Path) -> Path:
    """Scaffold a new vyperling project at ``base_dir/name``.

    Returns the created project root. Raises ForgeScaffoldError if it already exists.
    """
    project_root = base_dir / name
    if project_root.exists():
        raise ForgeScaffoldError(
            f"Cannot create project: {project_root} already exists."
        )

    env = _environment()
    context = {"name": name}

    for rel_path, template_name in _TEMPLATES:
        out_path = project_root / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        rendered = env.get_template(template_name).render(**context)
        out_path.write_text(rendered, encoding="utf-8")

    gitkeep = project_root / "mocks" / ".gitkeep"
    gitkeep.parent.mkdir(parents=True, exist_ok=True)
    gitkeep.write_text("", encoding="utf-8")

    return project_root
