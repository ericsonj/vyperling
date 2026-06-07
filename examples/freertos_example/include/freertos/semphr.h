#ifndef SEMPHR_H
#define SEMPHR_H

/* semphr.h is 100% macros delegating to queue.h underlying functions.
 * Do NOT mock this header — mock queue.h instead. */
#include "queue.h"

#define xSemaphoreCreateBinary() \
    xQueueGenericCreate(1, 0, queueQUEUE_TYPE_BINARY_SEMAPHORE)

#define xSemaphoreCreateMutex() \
    xQueueCreateMutex(queueQUEUE_TYPE_MUTEX)

#define xSemaphoreTake(xSemaphore, xBlockTime) \
    xQueueSemaphoreTake((xSemaphore), (xBlockTime))

#define xSemaphoreGive(xSemaphore) \
    xQueueGenericSend((xSemaphore), NULL, 0, queueSEND_TO_BACK)

#endif /* SEMPHR_H */
