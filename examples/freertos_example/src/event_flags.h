#ifndef EVENT_FLAGS_H
#define EVENT_FLAGS_H

#include "FreeRTOS.h"
#include "event_groups.h"

#define EVENT_FLAG_DATA_READY  ((EventBits_t)0x01)
#define EVENT_FLAG_TX_DONE     ((EventBits_t)0x02)
#define EVENT_FLAG_ERROR       ((EventBits_t)0x04)

typedef enum {
    EF_OK = 0,
    EF_ERR_NOT_INIT,
    EF_ERR_TIMEOUT,
} EventFlagsStatus;

EventFlagsStatus event_flags_init(void);
EventFlagsStatus event_flags_signal(EventBits_t bits);
EventFlagsStatus event_flags_wait_any(EventBits_t bits, uint32_t timeout_ms, EventBits_t *set_out);
EventFlagsStatus event_flags_wait_all(EventBits_t bits, uint32_t timeout_ms);

#endif /* EVENT_FLAGS_H */
