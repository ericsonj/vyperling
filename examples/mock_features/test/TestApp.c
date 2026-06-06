/* TestApp — drives the App SUT with all three dependencies mocked, exercising:
 *   - variadic mock        (Logger: log_printf)
 *   - function-pointer arg  (EventBus: register_cb)
 *   - struct-by-value mock  (Geometry: classify_point)
 */

#include "unity.h"
#include "App.h"
#include "Geometry.h"
#include "MockLogger.h"
#include "MockEventBus.h"
#include "MockGeometry.h"

void setUp(void)
{
}

void tearDown(void)
{
}

/* --- variadic dependency --- */
void testOnTickShouldLogWithFixedFormatString(void)
{
    /* Only the fixed param ("fmt") is asserted; the variadic tail is ignored. */
    log_printf_ExpectAndReturn("tick: %d", 0);
    log_printf_IgnoreArg_fmt(); /* fmt content not the point of this test */
    app_on_tick(42);
}

/* --- struct-by-value dependency --- */
void testScoreShouldClassifyPointByValue(void)
{
    struct Point p = {3, 4};
    classify_point_ExpectAndReturn(p, 1); /* struct compared by MEMORY */
    log_printf_ExpectAndReturn("score", 0);
    log_printf_IgnoreArg_fmt();
    TEST_ASSERT_EQUAL_INT(1, app_score(p));
}

/* --- function-pointer-param dependency --- */
static void my_handler(int code) { (void)code; }

void testInstallHandlerShouldRegisterTheCallback(void)
{
    register_cb_Expect(my_handler); /* callback identity asserted via PTR */
    app_install_handler(my_handler);
}
