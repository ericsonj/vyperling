/* Provides the struct Opaque body during Ceedling/CMock mock generation.
 *
 * vyperling only sees the forward declaration in Geometry.h (no support
 * include path), so it correctly skips use_opaque() with a warning.
 * Ceedling adds this directory to its include search, allowing CMock to
 * emit a compilable MockGeometry. The test (TestStructs.c) never calls
 * use_opaque_Expect, so the generated mock is simply unused — both tools
 * produce identical test outcomes for every function that is tested. */

#ifndef OPAQUE_STUB_H
#define OPAQUE_STUB_H

struct Opaque {
    int _stub;
};

#endif /* OPAQUE_STUB_H */
