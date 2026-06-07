#ifndef QUEUE_H
#define QUEUE_H

#include "FreeRTOS.h"

/* Queue type constants passed to xQueueGenericCreate */
#define queueQUEUE_TYPE_BASE           ((uint8_t)0)
#define queueQUEUE_TYPE_MUTEX          ((uint8_t)1)
#define queueQUEUE_TYPE_BINARY_SEMAPHORE ((uint8_t)3)

/* ---- Real underlying function declarations (mockable) ---- */

QueueHandle_t xQueueGenericCreate(
    UBaseType_t uxQueueLength,
    UBaseType_t uxItemSize,
    uint8_t ucQueueType
);

BaseType_t xQueueGenericSend(
    QueueHandle_t xQueue,
    const void *pvItemToQueue,
    TickType_t xTicksToWait,
    BaseType_t xCopyPosition
);

BaseType_t xQueueReceive(
    QueueHandle_t xQueue,
    void *pvBuffer,
    TickType_t xTicksToWait
);

BaseType_t xQueueSemaphoreTake(
    QueueHandle_t xQueue,
    TickType_t xTicksToWait
);

QueueHandle_t xQueueCreateMutex(uint8_t ucQueueType);

/* ---- Public macro wrappers (expand to underlying functions above) ---- */

#define queueSEND_TO_BACK ((BaseType_t)0)

#define xQueueCreate(uxQueueLength, uxItemSize) \
    xQueueGenericCreate((uxQueueLength), (uxItemSize), queueQUEUE_TYPE_BASE)

#define xQueueSend(xQueue, pvItemToQueue, xTicksToWait) \
    xQueueGenericSend((xQueue), (pvItemToQueue), (xTicksToWait), queueSEND_TO_BACK)

#endif /* QUEUE_H */
