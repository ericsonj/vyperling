#include "task_manager.h"

static void producer_task(void *pvParameters);
static void consumer_task(void *pvParameters);

TaskMgrStatus task_manager_init(void) {
    BaseType_t result;

    result = xTaskCreate(
        producer_task,
        "Producer",
        TASK_MANAGER_STACK_DEPTH,
        NULL,
        TASK_MGR_PRODUCER_PRIORITY,
        NULL
    );
    if (result != pdPASS) {
        return TASK_MGR_ERR_CREATE_FAILED;
    }

    result = xTaskCreate(
        consumer_task,
        "Consumer",
        TASK_MANAGER_STACK_DEPTH,
        NULL,
        TASK_MGR_CONSUMER_PRIORITY,
        NULL
    );
    if (result != pdPASS) {
        return TASK_MGR_ERR_CREATE_FAILED;
    }

    return TASK_MGR_OK;
}

void task_manager_run(void) {
    vTaskStartScheduler();
}

static void producer_task(void *pvParameters) {
    (void)pvParameters;
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

static void consumer_task(void *pvParameters) {
    (void)pvParameters;
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(200));
    }
}
