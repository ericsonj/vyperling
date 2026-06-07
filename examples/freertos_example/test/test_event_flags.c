#include "unity.h"
#include "mock_event_groups.h"
#include "event_flags.h"

static EventGroupHandle_t fake_group = (EventGroupHandle_t)0x0000CCCC;

void setUp(void)    { mock_event_groups_Init(); }
void tearDown(void) { mock_event_groups_Verify(); mock_event_groups_Destroy(); }

static void expect_init_ok(void) {
    xEventGroupCreate_ExpectAndReturn(fake_group);
}

void test_init_creates_event_group(void) {
    expect_init_ok();
    EventFlagsStatus status = event_flags_init();
    TEST_ASSERT_EQUAL(EF_OK, status);
}

void test_init_returns_error_on_null_group(void) {
    xEventGroupCreate_ExpectAndReturn(NULL);
    EventFlagsStatus status = event_flags_init();
    TEST_ASSERT_EQUAL(EF_ERR_NOT_INIT, status);
}

void test_signal_sets_bits(void) {
    expect_init_ok();
    event_flags_init();

    xEventGroupSetBits_ExpectAndReturn(fake_group, EVENT_FLAG_DATA_READY, EVENT_FLAG_DATA_READY);

    EventFlagsStatus status = event_flags_signal(EVENT_FLAG_DATA_READY);
    TEST_ASSERT_EQUAL(EF_OK, status);
}

void test_wait_any_returns_ok_when_bit_set(void) {
    expect_init_ok();
    event_flags_init();

    /* Return value has the waited bit set */
    xEventGroupWaitBits_ExpectAndReturn(
        fake_group,
        EVENT_FLAG_DATA_READY,
        pdTRUE,   /* clear on exit */
        pdFALSE,  /* wait any */
        pdMS_TO_TICKS(100),
        EVENT_FLAG_DATA_READY
    );

    EventBits_t got = 0;
    EventFlagsStatus status = event_flags_wait_any(EVENT_FLAG_DATA_READY, 100, &got);
    TEST_ASSERT_EQUAL(EF_OK, status);
    TEST_ASSERT_BITS(EVENT_FLAG_DATA_READY, EVENT_FLAG_DATA_READY, got);
}

void test_wait_any_returns_timeout_when_no_bits(void) {
    expect_init_ok();
    event_flags_init();

    xEventGroupWaitBits_ExpectAndReturn(
        fake_group,
        EVENT_FLAG_TX_DONE,
        pdTRUE, pdFALSE,
        pdMS_TO_TICKS(50),
        0  /* no bits set — timeout */
    );

    EventFlagsStatus status = event_flags_wait_any(EVENT_FLAG_TX_DONE, 50, NULL);
    TEST_ASSERT_EQUAL(EF_ERR_TIMEOUT, status);
}

void test_wait_all_returns_ok_when_all_bits_set(void) {
    expect_init_ok();
    event_flags_init();

    EventBits_t all = EVENT_FLAG_DATA_READY | EVENT_FLAG_TX_DONE;
    xEventGroupWaitBits_ExpectAndReturn(
        fake_group, all,
        pdTRUE, pdTRUE,
        pdMS_TO_TICKS(200),
        all
    );

    EventFlagsStatus status = event_flags_wait_all(all, 200);
    TEST_ASSERT_EQUAL(EF_OK, status);
}
