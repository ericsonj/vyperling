#include "event_flags.h"

static EventGroupHandle_t s_group = NULL;

EventFlagsStatus event_flags_init(void) {
    s_group = xEventGroupCreate();
    if (s_group == NULL) {
        return EF_ERR_NOT_INIT;
    }
    return EF_OK;
}

EventFlagsStatus event_flags_signal(EventBits_t bits) {
    if (s_group == NULL) {
        return EF_ERR_NOT_INIT;
    }
    xEventGroupSetBits(s_group, bits);
    return EF_OK;
}

EventFlagsStatus event_flags_wait_any(EventBits_t bits, uint32_t timeout_ms, EventBits_t *set_out) {
    if (s_group == NULL) {
        return EF_ERR_NOT_INIT;
    }
    EventBits_t result = xEventGroupWaitBits(
        s_group, bits,
        pdTRUE,   /* clear on exit */
        pdFALSE,  /* wait for any bit */
        pdMS_TO_TICKS(timeout_ms)
    );
    if (set_out != NULL) {
        *set_out = result;
    }
    return (result & bits) ? EF_OK : EF_ERR_TIMEOUT;
}

EventFlagsStatus event_flags_wait_all(EventBits_t bits, uint32_t timeout_ms) {
    if (s_group == NULL) {
        return EF_ERR_NOT_INIT;
    }
    EventBits_t result = xEventGroupWaitBits(
        s_group, bits,
        pdTRUE,  /* clear on exit */
        pdTRUE,  /* wait for ALL bits */
        pdMS_TO_TICKS(timeout_ms)
    );
    return ((result & bits) == bits) ? EF_OK : EF_ERR_TIMEOUT;
}
