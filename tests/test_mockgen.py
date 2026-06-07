"""Tests for vyperling.mockgen — pycparser-based CMock-compatible mock generator."""

from __future__ import annotations

import dataclasses
import shutil
import subprocess
import warnings
from pathlib import Path

import pytest

from vyperling.errors import ForgeMockgenError
from vyperling.mockgen import (
    FunctionDecl,
    _storage_type,
    _treat_as,
    generate_all,
    generate_mock,
    parse_header,
)
from vyperling.toolchains import get_toolchain
from vyperling.unity import (
    get_forge_mock_c_path,
    get_forge_mock_include_dir,
    get_unity_c_path,
    get_unity_include_dir,
)

HAVE_GCC = shutil.which("gcc") is not None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config(src: Path, defines: list[str] | None = None) -> dict:
    return {
        "project": {
            "src_dirs": [str(src)],
            "include_dirs": [str(src)],
            "mock_dir": str(src.parent / "mocks"),
        },
        "compiler": {
            "defines": defines or [],
            "extra_cflags": [],
        },
        "toolchains": {},
    }


def _native():
    return get_toolchain("native", {"toolchains": {}})


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


UART_H = """\
#include <stdint.h>
int  uart_send(const char *data, uint16_t len);
void uart_flush(void);
int  uart_read_byte(void);
int  uart_read_into(uint8_t *buf, uint16_t len);
int  printf_like(const char *fmt, ...);
void with_callback(int (*cb)(int));
"""


def _by_name(funcs: list[FunctionDecl]) -> dict[str, FunctionDecl]:
    return {f.name: f for f in funcs}


# ---------------------------------------------------------------------------
# Layer 1 — _treat_as mapping (pure, no compiler)
# ---------------------------------------------------------------------------

class TestTreatAs:
    def test_uint8(self):
        assert _treat_as("uint8_t") == "UINT8"

    def test_uint16(self):
        assert _treat_as("uint16_t") == "UINT16"

    def test_int(self):
        assert _treat_as("int") == "INT"

    def test_const_char_ptr_is_string(self):
        assert _treat_as("const char *") == "STRING"

    def test_char_ptr_is_string(self):
        assert _treat_as("char *") == "STRING"

    def test_other_ptr_is_ptr(self):
        assert _treat_as("uint8_t *") == "PTR"

    def test_strips_const(self):
        assert _treat_as("const uint16_t") == "UINT16"

    def test_unknown_type_is_memory(self):
        # Unknown types (structs, project enums) → byte-compare, no warning
        assert _treat_as("frobnicator_t") == "MEMORY"

    def test_unknown_type_no_warning(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert _treat_as("my_struct_t") == "MEMORY"  # must not warn

    def test_void_ptr_is_ptr(self):
        assert _treat_as("void *") == "PTR"


# ---------------------------------------------------------------------------
# Layer 2 — parse_header structural
# ---------------------------------------------------------------------------

class TestParseHeader:
    def test_parses_function_names(self, tmp_path):
        h = _write(tmp_path / "src" / "uart.h", UART_H)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            funcs = parse_header(h, _config(h.parent), _native())
        names = {f.name for f in funcs}
        assert {"uart_send", "uart_flush", "uart_read_byte", "uart_read_into"} <= names

    def test_void_function_is_void(self, tmp_path):
        h = _write(tmp_path / "src" / "uart.h", UART_H)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            funcs = _by_name(parse_header(h, _config(h.parent), _native()))
        assert funcs["uart_flush"].is_void is True
        assert funcs["uart_send"].is_void is False

    def test_void_param_collapses_to_no_args(self, tmp_path):
        h = _write(tmp_path / "src" / "uart.h", UART_H)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            funcs = _by_name(parse_header(h, _config(h.parent), _native()))
        assert funcs["uart_flush"].params == []
        assert funcs["uart_read_byte"].params == []

    def test_param_types_and_asserts(self, tmp_path):
        h = _write(tmp_path / "src" / "uart.h", UART_H)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            funcs = _by_name(parse_header(h, _config(h.parent), _native()))
        p = funcs["uart_send"].params
        assert p[0].name == "data"
        assert p[0].assert_suffix == "STRING"
        assert p[1].name == "len"
        assert p[1].assert_suffix == "UINT16"

    def test_variadic_not_skipped(self, tmp_path):
        h = _write(tmp_path / "src" / "uart.h", UART_H)
        funcs = _by_name(parse_header(h, _config(h.parent), _native()))
        assert funcs["printf_like"].skipped is False
        assert funcs["printf_like"].is_variadic is True

    def test_variadic_fixed_params_captured(self, tmp_path):
        h = _write(tmp_path / "src" / "uart.h", UART_H)
        funcs = _by_name(parse_header(h, _config(h.parent), _native()))
        p = funcs["printf_like"].params
        assert len(p) == 1
        assert p[0].name == "fmt"

    def test_fnptr_param_not_skipped(self, tmp_path):
        h = _write(tmp_path / "src" / "uart.h", UART_H)
        funcs = _by_name(parse_header(h, _config(h.parent), _native()))
        assert funcs["with_callback"].skipped is False

    def test_fnptr_param_is_fnptr_true(self, tmp_path):
        h = _write(tmp_path / "src" / "uart.h", UART_H)
        funcs = _by_name(parse_header(h, _config(h.parent), _native()))
        assert funcs["with_callback"].params[0].is_fnptr is True

    def test_fnptr_param_storage_type_void_ptr(self, tmp_path):
        h = _write(tmp_path / "src" / "uart.h", UART_H)
        funcs = _by_name(parse_header(h, _config(h.parent), _native()))
        assert funcs["with_callback"].params[0].storage_type == "void *"

    def test_fnptr_param_assert_suffix_PTR(self, tmp_path):
        h = _write(tmp_path / "src" / "uart.h", UART_H)
        funcs = _by_name(parse_header(h, _config(h.parent), _native()))
        assert funcs["with_callback"].params[0].assert_suffix == "PTR"

    def test_fnptr_no_return_thru(self, tmp_path):
        h = _write(tmp_path / "src" / "uart.h", UART_H)
        funcs = _by_name(parse_header(h, _config(h.parent), _native()))
        assert funcs["with_callback"].return_thru_params == []

    def test_return_thru_only_for_writable_ptr(self, tmp_path):
        h = _write(tmp_path / "src" / "uart.h", UART_H)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            funcs = _by_name(parse_header(h, _config(h.parent), _native()))
        # uart_read_into(uint8_t *buf, ...) -> buf is writable
        assert [p.name for p in funcs["uart_read_into"].return_thru_params] == ["buf"]
        # uart_send(const char *data, ...) -> const, no return-thru
        assert funcs["uart_send"].return_thru_params == []


# ---------------------------------------------------------------------------
# Layer 3 — system-include filtering (critical correctness guard)
# ---------------------------------------------------------------------------

class TestSystemIncludeFiltering:
    def test_only_project_functions_returned(self, tmp_path):
        h = _write(
            tmp_path / "src" / "thing.h",
            "#include <stdint.h>\n#include <stdio.h>\n"
            "uint32_t thing_compute(uint8_t a);\n",
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            funcs = parse_header(h, _config(h.parent), _native())
        names = [f.name for f in funcs]
        # No stdlib leakage (printf, fopen, etc.)
        assert names == ["thing_compute"]


# ---------------------------------------------------------------------------
# Layer 4 — generate_mock text structure
# ---------------------------------------------------------------------------

class TestGenerateMockText:
    def _gen(self, tmp_path):
        h = _write(tmp_path / "src" / "uart.h", UART_H)
        mock_dir = tmp_path / "mocks"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return generate_mock(h, mock_dir, _config(h.parent), _native())

    def test_writes_both_files(self, tmp_path):
        h_path, c_path = self._gen(tmp_path)
        assert h_path.is_file() and h_path.name == "mock_uart.h"
        assert c_path.is_file() and c_path.name == "mock_uart.c"

    def test_header_has_lifecycle(self, tmp_path):
        h_path, _ = self._gen(tmp_path)
        text = h_path.read_text()
        assert "void mock_uart_Init(void);" in text
        assert "void mock_uart_Verify(void);" in text
        assert "void mock_uart_Destroy(void);" in text

    def test_expect_and_return_for_nonvoid(self, tmp_path):
        h_path, _ = self._gen(tmp_path)
        text = h_path.read_text()
        assert "uart_send_ExpectAndReturn(" in text
        assert "int cmock_to_return" in text

    def test_expect_for_void(self, tmp_path):
        h_path, _ = self._gen(tmp_path)
        text = h_path.read_text()
        assert "void uart_flush_Expect(void);" in text
        # void function must NOT get ExpectAndReturn
        assert "uart_flush_ExpectAndReturn" not in text

    def test_return_thru_ptr_emitted(self, tmp_path):
        h_path, _ = self._gen(tmp_path)
        assert "uart_read_into_ReturnThruPtr_buf(" in h_path.read_text()

    def test_source_has_unity_asserts(self, tmp_path):
        _, c_path = self._gen(tmp_path)
        text = c_path.read_text()
        assert "UNITY_TEST_ASSERT_EQUAL_STRING" in text
        assert "UNITY_TEST_ASSERT_EQUAL_UINT16" in text

    def test_variadic_and_fnptr_now_in_header(self, tmp_path):
        h_path, _ = self._gen(tmp_path)
        text = h_path.read_text()
        assert "printf_like" in text
        assert "with_callback" in text

    def test_variadic_decl_has_ellipsis(self, tmp_path):
        _, c_path = self._gen(tmp_path)
        text = c_path.read_text()
        assert "printf_like(" in text
        assert "...)" in text

    def test_variadic_expect_has_only_fixed_params(self, tmp_path):
        h_path, _ = self._gen(tmp_path)
        text = h_path.read_text()
        assert "printf_like_ExpectAndReturn(" in text
        assert "cmock_to_return" in text
        # Ellipsis must NOT appear in the Expect signature
        lines = [l for l in text.splitlines() if "printf_like_ExpectAndReturn" in l]
        assert all("..." not in l for l in lines)

    def test_fnptr_struct_field_is_void_ptr(self, tmp_path):
        _, c_path = self._gen(tmp_path)
        text = c_path.read_text()
        assert "void *" in text and "expected_cb" in text

    def test_fnptr_assert_uses_equal_ptr(self, tmp_path):
        _, c_path = self._gen(tmp_path)
        assert "UNITY_TEST_ASSERT_EQUAL_PTR" in c_path.read_text()

    def test_fnptr_cast_in_expect(self, tmp_path):
        _, c_path = self._gen(tmp_path)
        assert "(void *)cb" in c_path.read_text()

    def test_generation_no_warn_without_skipped(self, tmp_path):
        h = _write(
            tmp_path / "src" / "clean.h",
            "int clean_fn(int x);\n",
        )
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            generate_mock(h, tmp_path / "mocks", _config(h.parent), _native())


# ---------------------------------------------------------------------------
# Layer 4b — opaque struct skip detection
# ---------------------------------------------------------------------------

OPAQUE_H = """\
struct Opaque;
void use_opaque(struct Opaque x);
void use_opaque_ptr(struct Opaque *x);
"""

TYPEDEF_OPAQUE_H = """\
typedef struct _Opaque Opaque_t;
void use_typedef_opaque(Opaque_t x);
void use_typedef_opaque_ptr(Opaque_t *x);
"""

COMPLETE_STRUCT_H = """\
struct Point { int x; int y; };
void move_point(struct Point p);
"""

TYPEDEF_COMPLETE_H = """\
typedef struct _Point { int x; int y; } Point_t;
void move_typedef_point(Point_t p);
"""

ANON_TYPEDEF_H = """\
typedef struct { int width; int height; } Size;
int area(Size s);
"""

OPAQUE_PTR_RTP_H = """\
struct Opaque;
void use_opaque_ptr(struct Opaque *o);
"""


class TestOpaqueStructDetection:
    def test_opaque_struct_by_value_is_skipped(self, tmp_path):
        h = _write(tmp_path / "src" / "opaque.h", OPAQUE_H)
        funcs = _by_name(parse_header(h, _config(h.parent), _native()))
        assert funcs["use_opaque"].skipped is True

    def test_opaque_skip_reason_mentions_incomplete(self, tmp_path):
        h = _write(tmp_path / "src" / "opaque.h", OPAQUE_H)
        funcs = _by_name(parse_header(h, _config(h.parent), _native()))
        assert "incomplete" in funcs["use_opaque"].skip_reason

    def test_opaque_ptr_not_skipped(self, tmp_path):
        h = _write(tmp_path / "src" / "opaque.h", OPAQUE_H)
        funcs = _by_name(parse_header(h, _config(h.parent), _native()))
        assert funcs["use_opaque_ptr"].skipped is False

    def test_typedef_opaque_by_value_is_skipped(self, tmp_path):
        h = _write(tmp_path / "src" / "opaque.h", TYPEDEF_OPAQUE_H)
        funcs = _by_name(parse_header(h, _config(h.parent), _native()))
        assert funcs["use_typedef_opaque"].skipped is True

    def test_typedef_opaque_ptr_not_skipped(self, tmp_path):
        h = _write(tmp_path / "src" / "opaque.h", TYPEDEF_OPAQUE_H)
        funcs = _by_name(parse_header(h, _config(h.parent), _native()))
        assert funcs["use_typedef_opaque_ptr"].skipped is False

    def test_complete_struct_not_skipped(self, tmp_path):
        h = _write(tmp_path / "src" / "point.h", COMPLETE_STRUCT_H)
        funcs = _by_name(parse_header(h, _config(h.parent), _native()))
        assert funcs["move_point"].skipped is False

    def test_complete_struct_treat_as_memory(self, tmp_path):
        h = _write(tmp_path / "src" / "point.h", COMPLETE_STRUCT_H)
        funcs = _by_name(parse_header(h, _config(h.parent), _native()))
        assert funcs["move_point"].params[0].assert_suffix == "MEMORY"

    def test_typedef_complete_struct_not_skipped(self, tmp_path):
        h = _write(tmp_path / "src" / "point.h", TYPEDEF_COMPLETE_H)
        funcs = _by_name(parse_header(h, _config(h.parent), _native()))
        assert funcs["move_typedef_point"].skipped is False

    def test_anon_typedef_struct_not_skipped(self, tmp_path):
        # `typedef struct { ... } Size;` is complete despite having no tag name.
        h = _write(tmp_path / "src" / "size.h", ANON_TYPEDEF_H)
        funcs = _by_name(parse_header(h, _config(h.parent), _native()))
        assert funcs["area"].skipped is False
        assert funcs["area"].params[0].assert_suffix == "MEMORY"

    def test_opaque_ptr_has_no_return_thru(self, tmp_path):
        # A pointer to an incomplete struct must NOT get ReturnThruPtr — its
        # pointee sizeof is unknown, so the `_thru` copy field can't be sized.
        h = _write(tmp_path / "src" / "op.h", OPAQUE_PTR_RTP_H)
        funcs = _by_name(parse_header(h, _config(h.parent), _native()))
        assert funcs["use_opaque_ptr"].skipped is False
        assert funcs["use_opaque_ptr"].return_thru_params == []

    def test_opaque_absent_from_generated_header(self, tmp_path):
        h = _write(tmp_path / "src" / "opaque.h", OPAQUE_H)
        with pytest.warns(UserWarning):
            h_path, _ = generate_mock(h, tmp_path / "mocks", _config(h.parent), _native())
        text = h_path.read_text()
        assert "use_opaque_Expect" not in text
        assert "use_opaque_ptr" in text  # pointer variant must still be there

    def test_opaque_ptr_present_in_generated_header(self, tmp_path):
        h = _write(tmp_path / "src" / "opaque.h", OPAQUE_H)
        with pytest.warns(UserWarning):
            h_path, _ = generate_mock(h, tmp_path / "mocks", _config(h.parent), _native())
        assert "use_opaque_ptr_Expect" in h_path.read_text()


# ---------------------------------------------------------------------------
# Layer 5 — end-to-end compile + run (gated on gcc)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAVE_GCC, reason="gcc not installed")
class TestEndToEnd:
    def _build(self, tmp_path, test_src: str) -> Path:
        src = tmp_path / "src"
        _write(src / "uart.h", UART_H)
        mock_dir = tmp_path / "mocks"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            generate_mock(src / "uart.h", mock_dir, _config(src), _native())
        test_c = _write(tmp_path / "test_uart.c", test_src)
        cdir = get_unity_include_dir()
        binary = tmp_path / "test_uart"
        cmd = [
            "gcc", "-Wall",
            f"-I{src}", f"-I{mock_dir}", f"-I{cdir}",
            str(test_c), str(mock_dir / "mock_uart.c"),
            str(get_unity_c_path()), str(get_forge_mock_c_path()),
            "-o", str(binary),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        return binary

    def test_passing_mock(self, tmp_path):
        src = """\
#include "unity.h"
#include "mock_uart.h"
void setUp(void)    { mock_uart_Init(); }
void tearDown(void) { mock_uart_Verify(); mock_uart_Destroy(); }
void test_ok(void) {
    uart_send_ExpectAndReturn("hi", 2, 5);
    TEST_ASSERT_EQUAL_INT(5, uart_send("hi", 2));
}
int main(void){ UNITY_BEGIN(); RUN_TEST(test_ok); return UNITY_END(); }
"""
        binary = self._build(tmp_path, src)
        proc = subprocess.run([str(binary)], capture_output=True, text=True)
        assert proc.returncode == 0
        assert "OK" in proc.stdout

    def test_return_thru_ptr(self, tmp_path):
        src = """\
#include "unity.h"
#include "mock_uart.h"
#include <stdint.h>
void setUp(void)    { mock_uart_Init(); }
void tearDown(void) { mock_uart_Verify(); mock_uart_Destroy(); }
void test_thru(void) {
    uint8_t out[1] = {0}; uint8_t want = 0xAB;
    uart_read_into_ExpectAndReturn(out, 1, 0);
    uart_read_into_ReturnThruPtr_buf(&want);
    uart_read_into(out, 1);
    TEST_ASSERT_EQUAL_UINT8(0xAB, out[0]);
}
int main(void){ UNITY_BEGIN(); RUN_TEST(test_thru); return UNITY_END(); }
"""
        binary = self._build(tmp_path, src)
        proc = subprocess.run([str(binary)], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stdout

    def test_arg_mismatch_fails(self, tmp_path):
        src = """\
#include "unity.h"
#include "mock_uart.h"
void setUp(void)    { mock_uart_Init(); }
void tearDown(void) { mock_uart_Verify(); mock_uart_Destroy(); }
void test_bad(void) {
    uart_send_ExpectAndReturn("hi", 2, 0);
    uart_send("bye", 2);
}
int main(void){ UNITY_BEGIN(); RUN_TEST(test_bad); return UNITY_END(); }
"""
        binary = self._build(tmp_path, src)
        proc = subprocess.run([str(binary)], capture_output=True, text=True)
        assert proc.returncode != 0
        assert "FAIL" in proc.stdout

    def test_ignore_arg_skips_one_param(self, tmp_path):
        src = """\
#include "unity.h"
#include "mock_uart.h"
#include <stdint.h>
void setUp(void)    { mock_uart_Init(); }
void tearDown(void) { mock_uart_Verify(); mock_uart_Destroy(); }
void test_ignore_len(void) {
    /* Expect a call; ignore the 'len' argument — any uint16 passes. */
    uart_send_ExpectAndReturn("hi", 2, 0);
    uart_send_IgnoreArg_len();
    TEST_ASSERT_EQUAL_INT(0, uart_send("hi", 99));  /* len differs — must pass */
}
int main(void){ UNITY_BEGIN(); RUN_TEST(test_ignore_len); return UNITY_END(); }
"""
        binary = self._build(tmp_path, src)
        proc = subprocess.run([str(binary)], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stdout

    def test_missing_call_fails_at_verify(self, tmp_path):
        src = """\
#include "unity.h"
#include "mock_uart.h"
void setUp(void)    { mock_uart_Init(); }
void tearDown(void) { mock_uart_Verify(); mock_uart_Destroy(); }
void test_missing(void) {
    uart_flush_Expect();
}
int main(void){ UNITY_BEGIN(); RUN_TEST(test_missing); return UNITY_END(); }
"""
        binary = self._build(tmp_path, src)
        proc = subprocess.run([str(binary)], capture_output=True, text=True)
        assert proc.returncode != 0
        assert "FAIL" in proc.stdout


# ---------------------------------------------------------------------------
# Layer 5b — E2E for variadic and fnptr (gated on gcc)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAVE_GCC, reason="gcc not installed")
class TestEndToEndVariadic:
    VARIADIC_HEADER = """\
int log_printf(const char *fmt, ...);
void log_event(int code, ...);
"""

    def _build(self, tmp_path, test_src: str) -> Path:
        src = tmp_path / "src"
        _write(src / "log.h", self.VARIADIC_HEADER)
        mock_dir = tmp_path / "mocks"
        generate_mock(src / "log.h", mock_dir, _config(src), _native())
        test_c = _write(tmp_path / "test_log.c", test_src)
        cdir = get_unity_include_dir()
        binary = tmp_path / "test_log"
        cmd = [
            "gcc", "-Wall",
            f"-I{src}", f"-I{mock_dir}", f"-I{cdir}",
            str(test_c), str(mock_dir / "mock_log.c"),
            str(get_unity_c_path()), str(get_forge_mock_c_path()),
            "-o", str(binary),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        return binary

    def test_variadic_compiles_and_passes(self, tmp_path):
        src = """\
#include "unity.h"
#include "mock_log.h"
void setUp(void)    { mock_log_Init(); }
void tearDown(void) { mock_log_Verify(); mock_log_Destroy(); }
void test_variadic(void) {
    log_printf_ExpectAndReturn("hello", 42);
    /* extra variadic args ignored by mock */
    TEST_ASSERT_EQUAL_INT(42, log_printf("hello", 1, 2, 3));
}
int main(void){ UNITY_BEGIN(); RUN_TEST(test_variadic); return UNITY_END(); }
"""
        binary = self._build(tmp_path, src)
        proc = subprocess.run([str(binary)], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stdout
        assert "OK" in proc.stdout

    def test_variadic_fixed_arg_mismatch_fails(self, tmp_path):
        src = """\
#include "unity.h"
#include "mock_log.h"
void setUp(void)    { mock_log_Init(); }
void tearDown(void) { mock_log_Verify(); mock_log_Destroy(); }
void test_mismatch(void) {
    log_printf_ExpectAndReturn("expected", 0);
    log_printf("actual", 99);
}
int main(void){ UNITY_BEGIN(); RUN_TEST(test_mismatch); return UNITY_END(); }
"""
        binary = self._build(tmp_path, src)
        proc = subprocess.run([str(binary)], capture_output=True, text=True)
        assert proc.returncode != 0
        assert "FAIL" in proc.stdout

    def test_void_variadic_expect(self, tmp_path):
        src = """\
#include "unity.h"
#include "mock_log.h"
void setUp(void)    { mock_log_Init(); }
void tearDown(void) { mock_log_Verify(); mock_log_Destroy(); }
void test_void_variadic(void) {
    log_event_Expect(7);
    log_event(7, "extra", 99);
}
int main(void){ UNITY_BEGIN(); RUN_TEST(test_void_variadic); return UNITY_END(); }
"""
        binary = self._build(tmp_path, src)
        proc = subprocess.run([str(binary)], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stdout


@pytest.mark.skipif(not HAVE_GCC, reason="gcc not installed")
class TestEndToEndFnptr:
    FNPTR_HEADER = """\
void register_cb(void (*cb)(int));
int transform(int (*fn)(int, int), int x, int y);
"""

    def _build(self, tmp_path, test_src: str) -> Path:
        src = tmp_path / "src"
        _write(src / "cb.h", self.FNPTR_HEADER)
        mock_dir = tmp_path / "mocks"
        generate_mock(src / "cb.h", mock_dir, _config(src), _native())
        test_c = _write(tmp_path / "test_cb.c", test_src)
        cdir = get_unity_include_dir()
        binary = tmp_path / "test_cb"
        cmd = [
            "gcc", "-Wall",
            f"-I{src}", f"-I{mock_dir}", f"-I{cdir}",
            str(test_c), str(mock_dir / "mock_cb.c"),
            str(get_unity_c_path()), str(get_forge_mock_c_path()),
            "-o", str(binary),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        return binary

    def test_fnptr_compiles_and_matches(self, tmp_path):
        src = """\
#include "unity.h"
#include "mock_cb.h"
static void my_cb(int x) { (void)x; }
void setUp(void)    { mock_cb_Init(); }
void tearDown(void) { mock_cb_Verify(); mock_cb_Destroy(); }
void test_fnptr(void) {
    register_cb_Expect(my_cb);
    register_cb(my_cb);
}
int main(void){ UNITY_BEGIN(); RUN_TEST(test_fnptr); return UNITY_END(); }
"""
        binary = self._build(tmp_path, src)
        proc = subprocess.run([str(binary)], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stdout
        assert "OK" in proc.stdout

    def test_fnptr_mismatch_fails(self, tmp_path):
        src = """\
#include "unity.h"
#include "mock_cb.h"
static void cb_a(int x) { (void)x; }
static void cb_b(int x) { (void)x; }
void setUp(void)    { mock_cb_Init(); }
void tearDown(void) { mock_cb_Verify(); mock_cb_Destroy(); }
void test_wrong_cb(void) {
    register_cb_Expect(cb_a);
    register_cb(cb_b);
}
int main(void){ UNITY_BEGIN(); RUN_TEST(test_wrong_cb); return UNITY_END(); }
"""
        binary = self._build(tmp_path, src)
        proc = subprocess.run([str(binary)], capture_output=True, text=True)
        assert proc.returncode != 0
        assert "FAIL" in proc.stdout

    def test_fnptr_with_return_value(self, tmp_path):
        src = """\
#include "unity.h"
#include "mock_cb.h"
static int add(int a, int b) { return a + b; }
void setUp(void)    { mock_cb_Init(); }
void tearDown(void) { mock_cb_Verify(); mock_cb_Destroy(); }
void test_transform(void) {
    transform_ExpectAndReturn(add, 3, 4, 99);
    TEST_ASSERT_EQUAL_INT(99, transform(add, 3, 4));
}
int main(void){ UNITY_BEGIN(); RUN_TEST(test_transform); return UNITY_END(); }
"""
        binary = self._build(tmp_path, src)
        proc = subprocess.run([str(binary)], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stdout
        assert "OK" in proc.stdout


@pytest.mark.skipif(not HAVE_GCC, reason="gcc not installed")
class TestEndToEndCompleteStruct:
    STRUCT_HEADER = """\
struct Point { int x; int y; };
void move_point(struct Point p);
int classify_point(struct Point p);
"""

    def _build(self, tmp_path, test_src: str) -> Path:
        src = tmp_path / "src"
        _write(src / "point.h", self.STRUCT_HEADER)
        mock_dir = tmp_path / "mocks"
        generate_mock(src / "point.h", mock_dir, _config(src), _native())
        test_c = _write(tmp_path / "test_point.c", test_src)
        cdir = get_unity_include_dir()
        binary = tmp_path / "test_point"
        cmd = [
            "gcc", "-Wall",
            f"-I{src}", f"-I{mock_dir}", f"-I{cdir}",
            str(test_c), str(mock_dir / "mock_point.c"),
            str(get_unity_c_path()), str(get_forge_mock_c_path()),
            "-o", str(binary),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        return binary

    def test_complete_struct_by_value_compiles(self, tmp_path):
        src = """\
#include "unity.h"
#include "mock_point.h"
void setUp(void)    { mock_point_Init(); }
void tearDown(void) { mock_point_Verify(); mock_point_Destroy(); }
void test_struct(void) {
    struct Point p = {3, 4};
    classify_point_ExpectAndReturn(p, 1);
    TEST_ASSERT_EQUAL_INT(1, classify_point(p));
}
int main(void){ UNITY_BEGIN(); RUN_TEST(test_struct); return UNITY_END(); }
"""
        binary = self._build(tmp_path, src)
        proc = subprocess.run([str(binary)], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stdout
        assert "OK" in proc.stdout

    def test_struct_mismatch_fails(self, tmp_path):
        src = """\
#include "unity.h"
#include "mock_point.h"
void setUp(void)    { mock_point_Init(); }
void tearDown(void) { mock_point_Verify(); mock_point_Destroy(); }
void test_struct_mismatch(void) {
    struct Point expected = {1, 2};
    struct Point actual   = {9, 9};
    classify_point_ExpectAndReturn(expected, 0);
    classify_point(actual);
}
int main(void){ UNITY_BEGIN(); RUN_TEST(test_struct_mismatch); return UNITY_END(); }
"""
        binary = self._build(tmp_path, src)
        proc = subprocess.run([str(binary)], capture_output=True, text=True)
        assert proc.returncode != 0
        assert "FAIL" in proc.stdout


# ---------------------------------------------------------------------------
# Layer 6 — _storage_type (pure)
# ---------------------------------------------------------------------------

class TestStorageType:
    def test_const_char_ptr(self):
        assert _storage_type("const char *") == "char *"

    def test_const_ptr_to_const(self):
        # const uint8_t *const → uint8_t *
        assert _storage_type("const uint8_t *const") == "uint8_t *"

    def test_plain_int(self):
        assert _storage_type("int") == "int"

    def test_plain_ptr(self):
        assert _storage_type("uint32_t *") == "uint32_t *"


# ---------------------------------------------------------------------------
# Layer 5c — transitive include filtering
# ---------------------------------------------------------------------------

class TestTransitiveIncludeFiltering:
    def test_only_target_header_functions_mocked(self, tmp_path):
        """Functions from #included headers must not appear in the mock."""
        dep = _write(
            tmp_path / "src" / "dep.h",
            "int dep_fn(void);\n",
        )
        top = _write(
            tmp_path / "src" / "top.h",
            f'#include "dep.h"\nint top_fn(void);\n',
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            funcs = parse_header(top, _config(top.parent), _native())
        names = [f.name for f in funcs]
        assert "top_fn" in names
        assert "dep_fn" not in names


# ---------------------------------------------------------------------------
# Layer 5d — compiler define pass-through
# ---------------------------------------------------------------------------

class TestDefinePassthrough:
    def test_gated_function_absent_without_define(self, tmp_path):
        h = _write(
            tmp_path / "src" / "guarded.h",
            "#ifdef PROJECT_DEF\nint real_fn(void);\n#endif\n",
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            funcs = parse_header(h, _config(h.parent), _native())
        assert not any(f.name == "real_fn" for f in funcs)

    def test_gated_function_present_with_define(self, tmp_path):
        h = _write(
            tmp_path / "src" / "guarded.h",
            "#ifdef PROJECT_DEF\nint real_fn(void);\n#endif\n",
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            funcs = parse_header(
                h, _config(h.parent, defines=["PROJECT_DEF"]), _native()
            )
        assert any(f.name == "real_fn" for f in funcs)


# ---------------------------------------------------------------------------
# Layer 5e — void * excluded from ReturnThruPtr
# ---------------------------------------------------------------------------

class TestVoidPtrReturnThru:
    def test_void_ptr_has_no_return_thru(self, tmp_path):
        h = _write(
            tmp_path / "src" / "buf.h",
            "int buf_read(void *buf, int len);\n",
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            funcs = _by_name(parse_header(h, _config(h.parent), _native()))
        assert funcs["buf_read"].return_thru_params == []

    def test_void_ptr_no_return_thru_in_generated_header(self, tmp_path):
        h = _write(
            tmp_path / "src" / "buf.h",
            "int buf_read(void *buf, int len);\n",
        )
        mock_dir = tmp_path / "mocks"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            h_path, _ = generate_mock(h, mock_dir, _config(h.parent), _native())
        assert "ReturnThruPtr_buf" not in h_path.read_text()


# ---------------------------------------------------------------------------
# Layer 5f — generate_all partial failure
# ---------------------------------------------------------------------------

class TestGenerateAllPartialFailure:
    def test_bad_header_skipped_good_one_generated(self, tmp_path):
        src = tmp_path / "src"
        good = _write(src / "good.h", "int good_fn(void);\n")
        bad = _write(src / "bad.h", "int oops(\n")  # truncated — parse error
        mock_dir = tmp_path / "mocks"
        with pytest.warns(UserWarning, match="skipping mock"):
            results = generate_all([good, bad], mock_dir, _config(src), _native())
        # Only the good header produced output
        assert len(results) == 1
        assert results[0][0].name == "mock_good.h"


# ---------------------------------------------------------------------------
# Layer 6 — forge_mock accessor tests
# ---------------------------------------------------------------------------

class TestForgeMockAccessors:
    def test_c_path_is_file(self):
        assert get_forge_mock_c_path().is_file()

    def test_c_path_filename(self):
        assert get_forge_mock_c_path().name == "forge_mock.c"

    def test_collocated_with_include_dir(self):
        assert get_forge_mock_c_path().parent == get_forge_mock_include_dir()

    def test_header_present(self):
        assert (get_forge_mock_include_dir() / "forge_mock.h").is_file()

    def test_content_has_runtime(self):
        assert "forge_mock_alloc" in get_forge_mock_c_path().read_text()


# ---------------------------------------------------------------------------
# Layer 7 — error handling
# ---------------------------------------------------------------------------

class TestMockPrefixConvention:
    """generate_mock() respects conventions.mock_prefix."""

    def _cfg_with_prefix(self, src: Path, mock_prefix: str) -> dict:
        cfg = _config(src)
        cfg["conventions"] = {"mock_prefix": mock_prefix}
        return cfg

    def test_mock_prefix_filenames(self, tmp_path):
        h = _write(tmp_path / "src" / "uart.h", "int uart_init(void);\n")
        mock_dir = tmp_path / "mocks"
        h_path, c_path = generate_mock(
            h, mock_dir, self._cfg_with_prefix(h.parent, "Mock"), _native()
        )
        assert h_path.name == "Mockuart.h"
        assert c_path.name == "Mockuart.c"

    def test_mock_prefix_lifecycle_in_header(self, tmp_path):
        h = _write(tmp_path / "src" / "uart.h", "int uart_init(void);\n")
        mock_dir = tmp_path / "mocks"
        h_path, _ = generate_mock(
            h, mock_dir, self._cfg_with_prefix(h.parent, "Mock"), _native()
        )
        text = h_path.read_text()
        assert "void Mockuart_Init(void);" in text
        assert "void Mockuart_Verify(void);" in text
        assert "void Mockuart_Destroy(void);" in text

    def test_mock_prefix_include_in_source(self, tmp_path):
        h = _write(tmp_path / "src" / "uart.h", "int uart_init(void);\n")
        mock_dir = tmp_path / "mocks"
        _, c_path = generate_mock(
            h, mock_dir, self._cfg_with_prefix(h.parent, "Mock"), _native()
        )
        assert '#include "Mockuart.h"' in c_path.read_text()

    def test_default_prefix_still_works(self, tmp_path):
        h = _write(tmp_path / "src" / "uart.h", "int uart_init(void);\n")
        mock_dir = tmp_path / "mocks"
        h_path, c_path = generate_mock(h, mock_dir, _config(h.parent), _native())
        assert h_path.name == "mock_uart.h"
        assert c_path.name == "mock_uart.c"


class TestErrors:
    def test_broken_header_raises(self, tmp_path):
        h = _write(tmp_path / "src" / "bad.h", "int oops(\n")  # truncated
        with pytest.raises(ForgeMockgenError):
            parse_header(h, _config(h.parent), _native())

    def test_bogus_compiler_raises(self, tmp_path):
        h = _write(tmp_path / "src" / "uart.h", UART_H)
        # replace() so we don't mutate the shared BUILTIN_TOOLCHAINS instance
        bogus = dataclasses.replace(
            get_toolchain("native", {"toolchains": {}}),
            cc="definitely-not-a-real-compiler-xyz",
        )
        with pytest.raises(ForgeMockgenError):
            parse_header(h, _config(h.parent), bogus)
