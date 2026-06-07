#ifndef TIMER_BLINK_H
#define TIMER_BLINK_H

#include "FreeRTOS.h"
#include "timers.h"

typedef void (*blink_callback_t)(void);

typedef enum {
    TB_OK = 0,
    TB_ERR_NOT_INIT,
    TB_ERR_CREATE_FAILED,
    TB_ERR_CMD_FAILED,
} TimerBlinkStatus;

TimerBlinkStatus timer_blink_init(uint32_t period_ms, blink_callback_t cb);
TimerBlinkStatus timer_blink_start(void);
TimerBlinkStatus timer_blink_stop(void);

#endif /* TIMER_BLINK_H */
