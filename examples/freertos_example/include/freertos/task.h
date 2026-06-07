#ifndef TASK_H
#define TASK_H

#include "FreeRTOS.h"

#define tskIDLE_PRIORITY ((UBaseType_t)0)
#define configMAX_PRIORITIES 7

/* Real function declarations — all mockable by vyperling mockgen. */

BaseType_t xTaskCreate(
    TaskFunction_t pxTaskCode,
    const char *pcName,
    uint16_t usStackDepth,
    void *pvParameters,
    UBaseType_t uxPriority,
    TaskHandle_t *pxCreatedTask
);

void vTaskDelete(TaskHandle_t xTaskToDelete);
void vTaskDelay(TickType_t xTicksToDelay);
void vTaskStartScheduler(void);
void vTaskSuspend(TaskHandle_t xTaskToSuspend);
void vTaskResume(TaskHandle_t xTaskToResume);
TickType_t xTaskGetTickCount(void);

#endif /* TASK_H */
