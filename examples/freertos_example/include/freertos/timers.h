#ifndef TIMERS_H
#define TIMERS_H

#include "FreeRTOS.h"

/* Timer command IDs passed to xTimerGenericCommand */
#define tmrCOMMAND_START         ((BaseType_t)1)
#define tmrCOMMAND_STOP          ((BaseType_t)2)
#define tmrCOMMAND_RESET         ((BaseType_t)3)

/* ---- Real underlying function declarations (mockable) ---- */

TimerHandle_t xTimerCreate(
    const char *pcTimerName,
    TickType_t xTimerPeriodInTicks,
    BaseType_t xAutoReload,
    void *pvTimerID,
    TimerCallbackFunction_t pxCallbackFunction
);

BaseType_t xTimerGenericCommand(
    TimerHandle_t xTimer,
    BaseType_t xCommandID,
    TickType_t xOptionalValue,
    BaseType_t *pxHigherPriorityTaskWoken,
    TickType_t xTicksToWait
);

void *pvTimerGetTimerID(TimerHandle_t xTimer);

/* ---- Public macro wrappers ---- */

#define xTimerStart(xTimer, xTicksToWait) \
    xTimerGenericCommand((xTimer), tmrCOMMAND_START, 0, NULL, (xTicksToWait))

#define xTimerStop(xTimer, xTicksToWait) \
    xTimerGenericCommand((xTimer), tmrCOMMAND_STOP, 0, NULL, (xTicksToWait))

#define xTimerReset(xTimer, xTicksToWait) \
    xTimerGenericCommand((xTimer), tmrCOMMAND_RESET, 0, NULL, (xTicksToWait))

#endif /* TIMERS_H */
