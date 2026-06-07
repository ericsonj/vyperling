/* TestLogger — variadic functions are mockable.
 * Fixed params are captured and asserted; the variadic tail is ignored. */

#include "unity.h"
#include "MockLogger.h"

void setUp(void)    { MockLogger_Init(); }
void tearDown(void) { MockLogger_Verify(); MockLogger_Destroy(); }

void testVariadicReturnsExpectedValue(void)
{
    log_printf_ExpectAndReturn("count=%d", 7);
    /* extra variadic args are ignored by the mock */
    TEST_ASSERT_EQUAL_INT(7, log_printf("count=%d", 1, 2, 3));
}

void testVariadicVoidReturnVariant(void)
{
    log_event_Expect(99);
    log_event(99, "ignored", 1, 2);
}
