#include "unity.h"
#include "mock_queue.h"
#include "queue_buffer.h"

static QueueHandle_t fake_queue = (QueueHandle_t)0xDEADBEEF;

void setUp(void)    { mock_queue_Init(); }
void tearDown(void) { mock_queue_Verify(); mock_queue_Destroy(); }

void test_init_creates_queue_with_correct_params(void) {
    xQueueGenericCreate_ExpectAndReturn(
        QUEUE_BUFFER_LENGTH, sizeof(uint32_t), queueQUEUE_TYPE_BASE,
        fake_queue
    );

    QueueBufferStatus status = queue_buffer_init();
    TEST_ASSERT_EQUAL(QB_OK, status);
}

void test_init_returns_error_on_null_queue(void) {
    xQueueGenericCreate_ExpectAndReturn(
        QUEUE_BUFFER_LENGTH, sizeof(uint32_t), queueQUEUE_TYPE_BASE,
        NULL
    );

    QueueBufferStatus status = queue_buffer_init();
    TEST_ASSERT_EQUAL(QB_ERR_NOT_INIT, status);
}

void test_push_sends_value(void) {
    xQueueGenericCreate_ExpectAndReturn(
        QUEUE_BUFFER_LENGTH, sizeof(uint32_t), queueQUEUE_TYPE_BASE,
        fake_queue
    );
    queue_buffer_init();

    xQueueGenericSend_ExpectAndReturn(
        fake_queue, NULL, pdMS_TO_TICKS(QUEUE_BUFFER_TIMEOUT_MS),
        queueSEND_TO_BACK,
        pdTRUE
    );
    xQueueGenericSend_IgnoreArg_pvItemToQueue();

    QueueBufferStatus status = queue_buffer_push(42u);
    TEST_ASSERT_EQUAL(QB_OK, status);
}

void test_push_returns_full_when_send_fails(void) {
    xQueueGenericCreate_ExpectAndReturn(
        QUEUE_BUFFER_LENGTH, sizeof(uint32_t), queueQUEUE_TYPE_BASE,
        fake_queue
    );
    queue_buffer_init();

    xQueueGenericSend_ExpectAndReturn(
        fake_queue, NULL, pdMS_TO_TICKS(QUEUE_BUFFER_TIMEOUT_MS),
        queueSEND_TO_BACK,
        pdFALSE
    );
    xQueueGenericSend_IgnoreArg_pvItemToQueue();

    QueueBufferStatus status = queue_buffer_push(99u);
    TEST_ASSERT_EQUAL(QB_ERR_FULL, status);
}

void test_pop_receives_value(void) {
    xQueueGenericCreate_ExpectAndReturn(
        QUEUE_BUFFER_LENGTH, sizeof(uint32_t), queueQUEUE_TYPE_BASE,
        fake_queue
    );
    queue_buffer_init();

    uint32_t out = 0;
    xQueueReceive_ExpectAndReturn(
        fake_queue, &out, pdMS_TO_TICKS(QUEUE_BUFFER_TIMEOUT_MS),
        pdTRUE
    );
    xQueueReceive_IgnoreArg_pvBuffer();

    QueueBufferStatus status = queue_buffer_pop(&out);
    TEST_ASSERT_EQUAL(QB_OK, status);
}

void test_pop_returns_empty_when_receive_fails(void) {
    xQueueGenericCreate_ExpectAndReturn(
        QUEUE_BUFFER_LENGTH, sizeof(uint32_t), queueQUEUE_TYPE_BASE,
        fake_queue
    );
    queue_buffer_init();

    uint32_t out = 0;
    xQueueReceive_ExpectAndReturn(
        fake_queue, &out, pdMS_TO_TICKS(QUEUE_BUFFER_TIMEOUT_MS),
        pdFALSE
    );
    xQueueReceive_IgnoreArg_pvBuffer();

    QueueBufferStatus status = queue_buffer_pop(&out);
    TEST_ASSERT_EQUAL(QB_ERR_EMPTY, status);
}
