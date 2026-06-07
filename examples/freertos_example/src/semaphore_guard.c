#include "semaphore_guard.h"

static QueueHandle_t s_binary_sem = NULL;
static QueueHandle_t s_mutex      = NULL;

SemGuardStatus sem_guard_init(void) {
    s_binary_sem = xSemaphoreCreateBinary();
    s_mutex      = xSemaphoreCreateMutex();
    if (s_binary_sem == NULL || s_mutex == NULL) {
        return SEM_ERR_NOT_INIT;
    }
    return SEM_OK;
}

SemGuardStatus sem_guard_acquire(void) {
    if (s_binary_sem == NULL) {
        return SEM_ERR_NOT_INIT;
    }
    BaseType_t taken = xSemaphoreTake(s_binary_sem, pdMS_TO_TICKS(SEM_GUARD_TIMEOUT_MS));
    return (taken == pdTRUE) ? SEM_OK : SEM_ERR_TIMEOUT;
}

SemGuardStatus sem_guard_release(void) {
    if (s_binary_sem == NULL) {
        return SEM_ERR_NOT_INIT;
    }
    xSemaphoreGive(s_binary_sem);
    return SEM_OK;
}

SemGuardStatus mutex_guard_lock(void) {
    if (s_mutex == NULL) {
        return SEM_ERR_NOT_INIT;
    }
    BaseType_t taken = xSemaphoreTake(s_mutex, pdMS_TO_TICKS(SEM_GUARD_TIMEOUT_MS));
    return (taken == pdTRUE) ? SEM_OK : SEM_ERR_TIMEOUT;
}

SemGuardStatus mutex_guard_unlock(void) {
    if (s_mutex == NULL) {
        return SEM_ERR_NOT_INIT;
    }
    xSemaphoreGive(s_mutex);
    return SEM_OK;
}
