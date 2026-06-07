#ifndef SEMAPHORE_GUARD_H
#define SEMAPHORE_GUARD_H

#include "FreeRTOS.h"
#include "semphr.h"

#define SEM_GUARD_TIMEOUT_MS 50

typedef enum {
    SEM_OK = 0,
    SEM_ERR_NOT_INIT,
    SEM_ERR_TIMEOUT,
} SemGuardStatus;

SemGuardStatus sem_guard_init(void);
SemGuardStatus sem_guard_acquire(void);
SemGuardStatus sem_guard_release(void);
SemGuardStatus mutex_guard_lock(void);
SemGuardStatus mutex_guard_unlock(void);

#endif /* SEMAPHORE_GUARD_H */
