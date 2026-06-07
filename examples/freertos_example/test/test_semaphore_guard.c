/* semaphore_guard uses xSemaphoreXxx macros which expand to queue.h underlying
 * functions at preprocessor time — so we mock queue.h, not semphr.h. */

#include "unity.h"
#include "mock_queue.h"
#include "semaphore_guard.h"

static QueueHandle_t fake_sem   = (QueueHandle_t)0x0000AAA1;
static QueueHandle_t fake_mutex = (QueueHandle_t)0x0000BBB2;

void setUp(void)    { mock_queue_Init(); }
void tearDown(void) { mock_queue_Verify(); mock_queue_Destroy(); }

static void expect_init_ok(void) {
    /* xSemaphoreCreateBinary → xQueueGenericCreate(1, 0, BINARY_SEMAPHORE) */
    xQueueGenericCreate_ExpectAndReturn(1, 0, queueQUEUE_TYPE_BINARY_SEMAPHORE, fake_sem);
    /* xSemaphoreCreateMutex → xQueueCreateMutex(MUTEX) */
    xQueueCreateMutex_ExpectAndReturn(queueQUEUE_TYPE_MUTEX, fake_mutex);
}

void test_init_creates_binary_sem_and_mutex(void) {
    expect_init_ok();
    SemGuardStatus status = sem_guard_init();
    TEST_ASSERT_EQUAL(SEM_OK, status);
}

void test_init_returns_error_when_sem_null(void) {
    xQueueGenericCreate_ExpectAndReturn(1, 0, queueQUEUE_TYPE_BINARY_SEMAPHORE, NULL);
    xQueueCreateMutex_ExpectAndReturn(queueQUEUE_TYPE_MUTEX, fake_mutex);

    SemGuardStatus status = sem_guard_init();
    TEST_ASSERT_EQUAL(SEM_ERR_NOT_INIT, status);
}

void test_acquire_takes_binary_semaphore(void) {
    expect_init_ok();
    sem_guard_init();

    /* xSemaphoreTake → xQueueSemaphoreTake */
    xQueueSemaphoreTake_ExpectAndReturn(fake_sem, pdMS_TO_TICKS(SEM_GUARD_TIMEOUT_MS), pdTRUE);
    TEST_ASSERT_EQUAL(SEM_OK, sem_guard_acquire());
}

void test_acquire_returns_timeout_on_failure(void) {
    expect_init_ok();
    sem_guard_init();

    xQueueSemaphoreTake_ExpectAndReturn(fake_sem, pdMS_TO_TICKS(SEM_GUARD_TIMEOUT_MS), pdFALSE);
    TEST_ASSERT_EQUAL(SEM_ERR_TIMEOUT, sem_guard_acquire());
}

void test_release_gives_binary_semaphore(void) {
    expect_init_ok();
    sem_guard_init();

    /* xSemaphoreGive → xQueueGenericSend(sem, NULL, 0, SEND_TO_BACK) */
    xQueueGenericSend_ExpectAndReturn(fake_sem, NULL, 0, queueSEND_TO_BACK, pdTRUE);
    TEST_ASSERT_EQUAL(SEM_OK, sem_guard_release());
}

void test_mutex_lock_takes_mutex(void) {
    expect_init_ok();
    sem_guard_init();

    xQueueSemaphoreTake_ExpectAndReturn(fake_mutex, pdMS_TO_TICKS(SEM_GUARD_TIMEOUT_MS), pdTRUE);
    TEST_ASSERT_EQUAL(SEM_OK, mutex_guard_lock());
}

void test_mutex_unlock_gives_mutex(void) {
    expect_init_ok();
    sem_guard_init();

    xQueueGenericSend_ExpectAndReturn(fake_mutex, NULL, 0, queueSEND_TO_BACK, pdTRUE);
    TEST_ASSERT_EQUAL(SEM_OK, mutex_guard_unlock());
}
