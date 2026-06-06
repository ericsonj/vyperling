/* TestGeometry — struct-by-value parameters.
 *
 * Complete structs (Point, Size) are byte-compared by the mock.
 * The opaque-struct-by-value function (use_opaque) is SKIPPED by mockgen with
 * a warning, so no use_opaque_Expect symbol exists — only the pointer variant
 * (use_opaque_ptr) is mocked. */

#include "unity.h"
#include "Geometry.h"
#include "MockGeometry.h"

void setUp(void)    { MockGeometry_Init(); }
void tearDown(void) { MockGeometry_Verify(); MockGeometry_Destroy(); }

void testClassifyPointStructByValue(void)
{
    struct Point p = {5, 6};
    classify_point_ExpectAndReturn(p, 1);
    TEST_ASSERT_EQUAL_INT(1, classify_point(p));
}

void testAnonymousTypedefStructByValue(void)
{
    Size s = {4, 3};
    area_ExpectAndReturn(s, 12);
    TEST_ASSERT_EQUAL_INT(12, area(s));
}

void testOpaqueStructPointerStillMocked(void)
{
    /* use_opaque(struct Opaque) is skipped; the pointer variant is fine. */
    struct Opaque *o = (struct Opaque *)0x1234;
    use_opaque_ptr_Expect(o);
    use_opaque_ptr(o);
}
