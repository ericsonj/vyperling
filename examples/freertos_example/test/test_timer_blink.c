#include "unity.h"
#include "mock_timers.h"
#include "timer_blink.h"

static TimerHandle_t fake_timer = (TimerHandle_t)0x0000DDDD;

static void dummy_cb(void) {}

void setUp(void)    { mock_timers_Init(); }
void tearDown(void) { mock_timers_Verify(); mock_timers_Destroy(); }

void test_init_creates_timer_with_correct_period(void) {
    xTimerCreate_ExpectAndReturn(
        "blink",
        pdMS_TO_TICKS(500),
        pdTRUE,   /* auto-reload */
        NULL,
        NULL,     /* internal callback — ignored below */
        fake_timer
    );
    xTimerCreate_IgnoreArg_pxCallbackFunction();
    xTimerCreate_IgnoreArg_pvTimerID();

    TimerBlinkStatus status = timer_blink_init(500, dummy_cb);
    TEST_ASSERT_EQUAL(TB_OK, status);
}

void test_init_returns_error_when_create_fails(void) {
    xTimerCreate_ExpectAndReturn(
        "blink", pdMS_TO_TICKS(200), pdTRUE, NULL, NULL,
        NULL
    );
    xTimerCreate_IgnoreArg_pxCallbackFunction();
    xTimerCreate_IgnoreArg_pvTimerID();

    TimerBlinkStatus status = timer_blink_init(200, dummy_cb);
    TEST_ASSERT_EQUAL(TB_ERR_CREATE_FAILED, status);
}

void test_start_sends_start_command(void) {
    xTimerCreate_ExpectAndReturn(
        "blink", pdMS_TO_TICKS(100), pdTRUE, NULL, NULL,
        fake_timer
    );
    xTimerCreate_IgnoreArg_pxCallbackFunction();
    xTimerCreate_IgnoreArg_pvTimerID();
    timer_blink_init(100, dummy_cb);

    /* xTimerStart → xTimerGenericCommand(timer, START, 0, NULL, 0) */
    xTimerGenericCommand_ExpectAndReturn(
        fake_timer, tmrCOMMAND_START, 0, NULL, 0,
        pdPASS
    );
    xTimerGenericCommand_IgnoreArg_pxHigherPriorityTaskWoken();

    TimerBlinkStatus status = timer_blink_start();
    TEST_ASSERT_EQUAL(TB_OK, status);
}

void test_stop_sends_stop_command(void) {
    xTimerCreate_ExpectAndReturn(
        "blink", pdMS_TO_TICKS(100), pdTRUE, NULL, NULL,
        fake_timer
    );
    xTimerCreate_IgnoreArg_pxCallbackFunction();
    xTimerCreate_IgnoreArg_pvTimerID();
    timer_blink_init(100, dummy_cb);

    xTimerGenericCommand_ExpectAndReturn(
        fake_timer, tmrCOMMAND_STOP, 0, NULL, 0,
        pdPASS
    );
    xTimerGenericCommand_IgnoreArg_pxHigherPriorityTaskWoken();

    TimerBlinkStatus status = timer_blink_stop();
    TEST_ASSERT_EQUAL(TB_OK, status);
}

void test_start_returns_error_on_command_failure(void) {
    xTimerCreate_ExpectAndReturn(
        "blink", pdMS_TO_TICKS(100), pdTRUE, NULL, NULL,
        fake_timer
    );
    xTimerCreate_IgnoreArg_pxCallbackFunction();
    xTimerCreate_IgnoreArg_pvTimerID();
    timer_blink_init(100, dummy_cb);

    xTimerGenericCommand_ExpectAndReturn(
        fake_timer, tmrCOMMAND_START, 0, NULL, 0,
        pdFAIL
    );
    xTimerGenericCommand_IgnoreArg_pxHigherPriorityTaskWoken();

    TimerBlinkStatus status = timer_blink_start();
    TEST_ASSERT_EQUAL(TB_ERR_CMD_FAILED, status);
}
