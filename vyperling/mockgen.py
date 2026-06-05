"""vyperling.mockgen — CMock-compatible C mock generator.

DIVERGENCE FROM ARCHITECTURE DOC: the original spec (sections 6.7 / 10) described a
simple regex parser with a weak API (``call_count`` + ``EXPECT_*_CALLED``). This module
supersedes that. It uses **pycparser** (with the resolved toolchain's ``cc -E`` as the
preprocessor and ``pycparser_fake_libc`` for the standard library) and **jinja2** to emit a
full queue-based CMock-style API per mocked function:

    func_Expect(args)            / func_ExpectAndReturn(args, ret)   (void / non-void)
    func_ExpectAnyArgs[AndReturn]
    func_Ignore / func_IgnoreAndReturn / func_StopIgnore
    func_ReturnThruPtr_<param>   (non-const pointer params only)
    func_AddCallback / func_Stub
    mock_<module>_Init / _Verify / _Destroy

Failures route through Unity (UNITY_TEST_FAIL). The shared runtime lives in the vendored
``vyperling/c/forge_mock.{c,h}`` and is compiled into every test binary.

v0.1 limitations (functions affected are skipped with a warning, not mocked):
  - variadic functions (``...``)
  - function-pointer parameters
  - incomplete struct-by-value parameters
ReturnThruPtr copies a single element. Pointer args are compared by identity except
``const char *`` (string compare). float/double asserts assume UNITY_INCLUDE_FLOAT/_DOUBLE.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path

import pycparser
import pycparser_fake_libc
from jinja2 import Environment, PackageLoader, StrictUndefined
from pycparser import c_ast, c_generator

from vyperling.config import get_include_dirs, get_src_dirs
from vyperling.errors import ForgeMockgenError
from vyperling.toolchains import Toolchain

# Default C type -> Unity assertion suffix. Typedef names are matched before base
# types so uint16_t wins over its underlying `unsigned short`.
TREAT_AS: dict[str, str] = {
    "char": "INT8",
    "signed char": "INT8",
    "int8_t": "INT8",
    "unsigned char": "UINT8",
    "uint8_t": "UINT8",
    "short": "INT16",
    "short int": "INT16",
    "int16_t": "INT16",
    "unsigned short": "UINT16",
    "uint16_t": "UINT16",
    "int": "INT",
    "signed int": "INT",
    "int32_t": "INT32",
    "long": "INT",
    "unsigned": "UINT",
    "unsigned int": "UINT",
    "uint32_t": "UINT32",
    "size_t": "UINT",
    "long long": "INT64",
    "int64_t": "INT64",
    "unsigned long long": "UINT64",
    "uint64_t": "UINT64",
    "float": "FLOAT",
    "double": "DOUBLE",
}


@dataclass
class Param:
    name: str
    type: str
    assert_suffix: str
    is_ptr: bool = False
    is_const_ptr: bool = False
    return_thru: bool = False
    pointee_type: str = ""
    storage_type: str = ""


@dataclass
class FunctionDecl:
    name: str
    return_type: str
    params: list[Param]
    is_void: bool
    skipped: bool = False
    skip_reason: str | None = None
    return_thru_params: list[Param] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _cpp_args(config: dict) -> list[str]:
    args = [
        "-E",
        "-nostdinc",
        "-I" + pycparser_fake_libc.directory,
        "-D__attribute__(x)=",
        "-D__extension__=",
        "-D__inline=",
        "-D__inline__=",
        "-D__restrict=",
        "-D__asm__(x)=",
    ]
    for d in config["compiler"]["defines"]:
        args.append("-D" + str(d))
    for d in get_include_dirs(config):
        args.append("-I" + str(d.resolve()))
    for d in get_src_dirs(config):
        args.append("-I" + str(d.resolve()))
    # Pass through -D and -U extra_cflags (skip -include and other flags that
    # are incompatible with the pycparser fake-libc -nostdinc environment).
    for flag in config["compiler"].get("extra_cflags", []):
        flag = str(flag).strip()
        if flag.startswith(("-D", "-U")):
            args.append(flag)
    return args


def _strip_quals(type_str: str) -> str:
    """Normalise a rendered C type for TREAT_AS lookup."""
    tokens = [t for t in type_str.replace("*", " ").split() if t not in ("const", "volatile")]
    return " ".join(tokens).strip()


def _storage_type(type_str: str) -> str:
    """A writable copy type for a struct member: drop all `const` qualifiers but
    keep `*` so pointer arity is preserved (`const char *const` -> `char *`)."""
    out = type_str.replace("*", " * ")
    tokens = [t for t in out.split() if t != "const"]
    rendered = " ".join(tokens)
    return rendered.replace(" * ", " *").replace(" *", " *").strip()


def _treat_as(type_str: str) -> str:
    norm = _strip_quals(type_str)
    if "*" in type_str:
        if norm in ("char",) and "const" in type_str:
            return "STRING"
        if norm == "char":
            return "STRING"
        return "PTR"
    if norm in TREAT_AS:
        return TREAT_AS[norm]
    # Unknown non-pointer type (typically a struct/union or project enum/typedef).
    # Mirror CMock's `memcmp_if_unknown: true` — compare the raw bytes. This keeps
    # struct-by-value parameters working instead of mis-treating them as int.
    return "MEMORY"


def _is_void_param(param) -> bool:
    t = param.type
    return (
        isinstance(t, c_ast.TypeDecl)
        and isinstance(t.type, c_ast.IdentifierType)
        and t.type.names == ["void"]
    )


def _is_fnptr_param(param) -> bool:
    return isinstance(param.type, c_ast.PtrDecl) and isinstance(
        param.type.type, c_ast.FuncDecl
    )


def _build_param(param, index: int, gen: c_generator.CGenerator) -> Param:
    name = param.name or f"cmock_arg{index}"
    type_str = gen.visit(param.type)
    is_ptr = isinstance(param.type, c_ast.PtrDecl)
    is_const_ptr = False
    pointee_type = ""
    if is_ptr:
        pointee = param.type.type
        is_const_ptr = "const" in getattr(pointee, "quals", [])
        pointee_type = gen.visit(pointee)
    assert_suffix = _treat_as(type_str)
    # ReturnThruPtr only for writable (non-const) pointers that aren't strings,
    # and never for `void *` (sizeof(void) is illegal — can't size the copy).
    pointee_is_void = is_ptr and _strip_quals(pointee_type) == "void"
    return_thru = (
        is_ptr and not is_const_ptr and assert_suffix != "STRING" and not pointee_is_void
    )
    return Param(
        name=name,
        type=type_str,
        assert_suffix=assert_suffix,
        is_ptr=is_ptr,
        is_const_ptr=is_const_ptr,
        return_thru=return_thru,
        pointee_type=pointee_type,
        storage_type=_storage_type(type_str),
    )


def _extract_functions(ast, fake_dir: str, target: Path | None = None) -> list[FunctionDecl]:
    gen = c_generator.CGenerator()
    out: list[FunctionDecl] = []
    target_resolved = target.resolve() if target is not None else None

    for ext in ast.ext:
        if not isinstance(ext, c_ast.Decl):
            continue
        if not isinstance(ext.type, c_ast.FuncDecl):
            continue
        # Exclude anything that came from the fake libc (stdlib) — the key guard.
        coord = ext.coord
        if coord is not None and coord.file and fake_dir in str(coord.file):
            continue
        # Only mock functions declared in THIS header, not ones pulled in via
        # transitive #includes (e.g. osal.h). Otherwise every mock would redefine
        # the included headers' functions and collide at link time. Mirrors CMock,
        # which mocks a single header's own declarations.
        if target_resolved is not None and coord is not None and coord.file:
            try:
                if Path(coord.file).resolve() != target_resolved:
                    continue
            except OSError:
                if Path(coord.file).name != target_resolved.name:
                    continue

        func = ext.type
        name = ext.name
        return_type = gen.visit(func.type).strip()
        is_void = return_type == "void"

        raw_params = func.args.params if func.args else []
        # f(void) and f() both mean no args.
        if len(raw_params) == 1 and _is_void_param(raw_params[0]):
            raw_params = []

        skip_reason: str | None = None
        params: list[Param] = []
        for i, p in enumerate(raw_params):
            if isinstance(p, c_ast.EllipsisParam):
                skip_reason = "variadic functions are not supported"
                break
            if _is_fnptr_param(p):
                skip_reason = "function-pointer parameters are not supported"
                break
            params.append(_build_param(p, i, gen))

        if skip_reason is not None:
            out.append(
                FunctionDecl(
                    name=name,
                    return_type=return_type,
                    params=[],
                    is_void=is_void,
                    skipped=True,
                    skip_reason=skip_reason,
                )
            )
            continue

        out.append(
            FunctionDecl(
                name=name,
                return_type=return_type,
                params=params,
                is_void=is_void,
                return_thru_params=[p for p in params if p.return_thru],
            )
        )

    return out


def parse_header(header_path: Path, config: dict, toolchain: Toolchain) -> list[FunctionDecl]:
    """Parse a C header into FunctionDecls. Skipped funcs are returned with skipped=True."""
    try:
        ast = pycparser.parse_file(
            str(header_path),
            use_cpp=True,
            cpp_path=toolchain.cc,
            cpp_args=_cpp_args(config),
        )
    except Exception as exc:  # noqa: BLE001 — pycparser/cpp raise many types
        raise ForgeMockgenError(f"Failed to parse {header_path}: {exc}") from exc
    return _extract_functions(ast, pycparser_fake_libc.directory, header_path)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def _ptr_to_pointee(type_str: str) -> str:
    """Drop one trailing '*' from a pointer type ('int *' -> 'int')."""
    idx = type_str.rfind("*")
    return type_str[:idx].strip() if idx != -1 else type_str


def _decl_params(f: FunctionDecl) -> str:
    if not f.params:
        return "void"
    return ", ".join(f"{p.type} {p.name}" for p in f.params)


def _expect_params(f: FunctionDecl) -> str:
    if not f.params:
        return "void"
    return ", ".join(f"{p.type} {p.name}" for p in f.params)


def _expect_and_return_params(f: FunctionDecl) -> str:
    parts = [f"{p.type} {p.name}" for p in f.params]
    parts.append(f"{f.return_type} cmock_to_return")
    return ", ".join(parts)


def _callback_var_decl(f: FunctionDecl, var: str) -> str:
    """A full declaration of a function-pointer variable, e.g.
    'int (*uart_send_callback)(const char *, uint16_t, int)'."""
    arg_types = [p.type for p in f.params]
    arg_types.append("int")  # cmock_num_calls
    return f"{f.return_type} (*{var})({', '.join(arg_types)})"


def _callback_sig(f: FunctionDecl) -> str:
    arg_types = [p.type for p in f.params]
    arg_types.append("int cmock_num_calls")
    return f"{f.return_type} (*cb)({', '.join(arg_types)})"


def _callback_call_args(f: FunctionDecl) -> str:
    args = [p.name for p in f.params]
    args.append(f"{f.name}_callback_calls++")
    return ", ".join(args)


def _build_context(
    module: str, header_name: str, funcs: list[FunctionDecl], mock_prefix: str = "mock_"
) -> dict:
    active = [f for f in funcs if not f.skipped]
    fctx = []
    for f in active:
        params_ctx = []
        for p in f.params:
            params_ctx.append(
                {
                    "name": p.name,
                    "type": p.type,
                    "storage_type": p.storage_type,
                    "assert_suffix": p.assert_suffix,
                    "is_ptr": p.is_ptr,
                    "is_const_ptr": p.is_const_ptr,
                }
            )
        rtp_ctx = [
            {"name": p.name, "type": p.type, "pointee_type": _ptr_to_pointee(p.type)}
            for p in f.return_thru_params
        ]
        fctx.append(
            {
                "name": f.name,
                "return_type": f.return_type,
                "is_void": f.is_void,
                "has_args": bool(f.params),
                "params": params_ctx,
                "return_thru_params": rtp_ctx,
                "decl_params": _decl_params(f),
                "expect_params": _expect_params(f),
                "expect_and_return_params": _expect_and_return_params(f),
                "callback_var_decl": _callback_var_decl(f, f"{f.name}_callback"),
                "callback_sig": _callback_sig(f),
                "callback_call_args": _callback_call_args(f),
            }
        )
    return {
        "module": module,
        "header_name": header_name,
        "guard": f"MOCK_{module.upper()}_H",
        "mock_prefix": mock_prefix,
        "functions": fctx,
    }


_env: Environment | None = None


def _environment() -> Environment:
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


def generate_mock(
    header_path: Path,
    mock_dir: Path,
    config: dict,
    toolchain: Toolchain,
) -> tuple[Path, Path]:
    """Generate <mock_prefix><module>.h and <mock_prefix><module>.c. Returns their paths."""
    mock_prefix: str = config.get("conventions", {}).get("mock_prefix", "mock_")
    module = header_path.stem
    funcs = parse_header(header_path, config, toolchain)

    for f in funcs:
        if f.skipped:
            warnings.warn(
                f"vyperling mockgen: skipping '{f.name}' in {header_path.name} — {f.skip_reason}",
                UserWarning,
                stacklevel=2,
            )

    context = _build_context(module, header_path.name, funcs, mock_prefix)
    env = _environment()
    header_out = env.get_template("mock_header.h.j2").render(**context)
    source_out = env.get_template("mock_source.c.j2").render(**context)

    mock_dir.mkdir(parents=True, exist_ok=True)
    h_path = mock_dir / f"{mock_prefix}{module}.h"
    c_path = mock_dir / f"{mock_prefix}{module}.c"
    h_path.write_text(header_out, encoding="utf-8")
    c_path.write_text(source_out, encoding="utf-8")
    return h_path, c_path


def generate_all(
    headers: list[Path],
    mock_dir: Path,
    config: dict,
    toolchain: Toolchain,
) -> list[tuple[Path, Path]]:
    """Generate mocks for every header. Returns a list of (mock.h, mock.c) tuples.

    A header that fails to parse (e.g. it pulls in a missing dependency) is
    skipped with a warning rather than aborting the whole run — the tests that
    depend on its mock will simply fail to compile in isolation.
    """
    results: list[tuple[Path, Path]] = []
    for header in headers:
        try:
            results.append(generate_mock(header, mock_dir, config, toolchain))
        except ForgeMockgenError as exc:
            warnings.warn(
                f"vyperling mockgen: skipping mock for {header} — {exc}",
                UserWarning,
                stacklevel=2,
            )
    return results
