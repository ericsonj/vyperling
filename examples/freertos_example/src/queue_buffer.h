#ifndef QUEUE_BUFFER_H
#define QUEUE_BUFFER_H

#include "FreeRTOS.h"
#include "queue.h"

#define QUEUE_BUFFER_LENGTH 8
#define QUEUE_BUFFER_TIMEOUT_MS 100

typedef enum {
    QB_OK = 0,
    QB_ERR_NOT_INIT,
    QB_ERR_FULL,
    QB_ERR_EMPTY,
} QueueBufferStatus;

QueueBufferStatus queue_buffer_init(void);
QueueBufferStatus queue_buffer_push(uint32_t value);
QueueBufferStatus queue_buffer_pop(uint32_t *out);

#endif /* QUEUE_BUFFER_H */
