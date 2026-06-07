#include "queue_buffer.h"

static QueueHandle_t s_queue = NULL;

QueueBufferStatus queue_buffer_init(void) {
    s_queue = xQueueCreate(QUEUE_BUFFER_LENGTH, sizeof(uint32_t));
    if (s_queue == NULL) {
        return QB_ERR_NOT_INIT;
    }
    return QB_OK;
}

QueueBufferStatus queue_buffer_push(uint32_t value) {
    if (s_queue == NULL) {
        return QB_ERR_NOT_INIT;
    }
    BaseType_t sent = xQueueSend(s_queue, &value, pdMS_TO_TICKS(QUEUE_BUFFER_TIMEOUT_MS));
    return (sent == pdTRUE) ? QB_OK : QB_ERR_FULL;
}

QueueBufferStatus queue_buffer_pop(uint32_t *out) {
    if (s_queue == NULL) {
        return QB_ERR_NOT_INIT;
    }
    BaseType_t rcvd = xQueueReceive(s_queue, out, pdMS_TO_TICKS(QUEUE_BUFFER_TIMEOUT_MS));
    return (rcvd == pdTRUE) ? QB_OK : QB_ERR_EMPTY;
}
