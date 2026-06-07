#include "timer_blink.h"

static TimerHandle_t   s_timer = NULL;
static blink_callback_t s_user_cb = NULL;

static void internal_cb(TimerHandle_t xTimer) {
    (void)xTimer;
    if (s_user_cb != NULL) {
        s_user_cb();
    }
}

TimerBlinkStatus timer_blink_init(uint32_t period_ms, blink_callback_t cb) {
    s_user_cb = cb;
    s_timer = xTimerCreate(
        "blink",
        pdMS_TO_TICKS(period_ms),
        pdTRUE,       /* auto-reload */
        NULL,
        internal_cb
    );
    if (s_timer == NULL) {
        return TB_ERR_CREATE_FAILED;
    }
    return TB_OK;
}

TimerBlinkStatus timer_blink_start(void) {
    if (s_timer == NULL) {
        return TB_ERR_NOT_INIT;
    }
    BaseType_t ok = xTimerStart(s_timer, 0);
    return (ok == pdPASS) ? TB_OK : TB_ERR_CMD_FAILED;
}

TimerBlinkStatus timer_blink_stop(void) {
    if (s_timer == NULL) {
        return TB_ERR_NOT_INIT;
    }
    BaseType_t ok = xTimerStop(s_timer, 0);
    return (ok == pdPASS) ? TB_OK : TB_ERR_CMD_FAILED;
}
