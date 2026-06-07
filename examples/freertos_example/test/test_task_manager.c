#include "unity.h"
#include "mock_task.h"
#include "task_manager.h"

void setUp(void)    { mock_task_Init(); }
void tearDown(void) { mock_task_Verify(); mock_task_Destroy(); }

void test_init_creates_two_tasks(void) {
    xTaskCreate_ExpectAndReturn(
        NULL, "Producer", TASK_MANAGER_STACK_DEPTH, NULL,
        TASK_MGR_PRODUCER_PRIORITY, NULL,
        pdPASS
    );
    xTaskCreate_IgnoreArg_pxTaskCode();
    xTaskCreate_IgnoreArg_pxCreatedTask();

    xTaskCreate_ExpectAndReturn(
        NULL, "Consumer", TASK_MANAGER_STACK_DEPTH, NULL,
        TASK_MGR_CONSUMER_PRIORITY, NULL,
        pdPASS
    );
    xTaskCreate_IgnoreArg_pxTaskCode();
    xTaskCreate_IgnoreArg_pxCreatedTask();

    TaskMgrStatus status = task_manager_init();
    TEST_ASSERT_EQUAL(TASK_MGR_OK, status);
}

void test_init_returns_error_when_first_create_fails(void) {
    xTaskCreate_ExpectAndReturn(
        NULL, "Producer", TASK_MANAGER_STACK_DEPTH, NULL,
        TASK_MGR_PRODUCER_PRIORITY, NULL,
        pdFAIL
    );
    xTaskCreate_IgnoreArg_pxTaskCode();
    xTaskCreate_IgnoreArg_pxCreatedTask();

    TaskMgrStatus status = task_manager_init();
    TEST_ASSERT_EQUAL(TASK_MGR_ERR_CREATE_FAILED, status);
}

void test_run_calls_start_scheduler(void) {
    vTaskStartScheduler_Expect();
    task_manager_run();
}
