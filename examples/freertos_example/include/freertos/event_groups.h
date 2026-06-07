#ifndef EVENT_GROUPS_H
#define EVENT_GROUPS_H

#include "FreeRTOS.h"

/* Real function declarations — all mockable by vyperling mockgen. */

EventGroupHandle_t xEventGroupCreate(void);

EventBits_t xEventGroupSetBits(
    EventGroupHandle_t xEventGroup,
    EventBits_t uxBitsToSet
);

EventBits_t xEventGroupWaitBits(
    EventGroupHandle_t xEventGroup,
    EventBits_t uxBitsToWaitFor,
    BaseType_t xClearOnExit,
    BaseType_t xWaitForAllBits,
    TickType_t xTicksToWait
);

EventBits_t xEventGroupClearBits(
    EventGroupHandle_t xEventGroup,
    EventBits_t uxBitsToClear
);

#endif /* EVENT_GROUPS_H */
