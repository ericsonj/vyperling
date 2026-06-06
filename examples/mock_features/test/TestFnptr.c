/* TestEventBus — function-pointer parameters are mockable.
 * The callback pointer is asserted by identity (PTR compare). */

#include "unity.h"
#include "MockEventBus.h"

void setUp(void)    { MockEventBus_Init(); }
void tearDown(void) { MockEventBus_Verify(); MockEventBus_Destroy(); }

static void handler_a(int x) { (void)x; }
static void handler_b(int x) { (void)x; }
static int  adder(int a, int b) { return a + b; }

void testRegisterCbMatchesCallbackByIdentity(void)
{
    register_cb_Expect(handler_a);
    register_cb(handler_a);
}

void testRegisterCbCanIgnoreCallbackArg(void)
{
    register_cb_Expect(handler_a);
    register_cb_IgnoreArg_cb();
    register_cb(handler_b); /* different callback — passes because ignored */
}

void testTransformWithFnptrAndReturnValue(void)
{
    transform_ExpectAndReturn(adder, 3, 4, 100);
    TEST_ASSERT_EQUAL_INT(100, transform(adder, 3, 4));
}
