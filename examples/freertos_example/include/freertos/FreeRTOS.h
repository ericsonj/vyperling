#ifndef FREERTOS_H
#define FREERTOS_H

#include <stdint.h>
#include <stddef.h>

/* Minimal FreeRTOS stub types for vyperling unit testing.
 * These are NOT the real FreeRTOS headers — they reproduce only the
 * signatures needed by the example modules so mockgen can parse them. */

typedef uint32_t TickType_t;
typedef uint32_t UBaseType_t;
typedef int32_t  BaseType_t;
typedef uint32_t EventBits_t;

typedef void *TaskHandle_t;
typedef void *QueueHandle_t;
typedef void *EventGroupHandle_t;
typedef void *TimerHandle_t;

typedef void (*TaskFunction_t)(void *pvParameters);
typedef void (*TimerCallbackFunction_t)(TimerHandle_t xTimer);

#define pdTRUE  ((BaseType_t)1)
#define pdFALSE ((BaseType_t)0)
#define pdPASS  pdTRUE
#define pdFAIL  pdFALSE

#define portMAX_DELAY    ((TickType_t)0xFFFFFFFFUL)
#define pdMS_TO_TICKS(ms) ((TickType_t)(ms))

/* configSUPPORT_DYNAMIC_ALLOCATION must be 1 for xTaskCreate / xQueueGenericCreate */
#ifndef configSUPPORT_DYNAMIC_ALLOCATION
#define configSUPPORT_DYNAMIC_ALLOCATION 1
#endif

#ifndef configUSE_MUTEXES
#define configUSE_MUTEXES 1
#endif

#ifndef configUSE_TIMERS
#define configUSE_TIMERS 1
#endif

#ifndef configUSE_EVENT_GROUPS
#define configUSE_EVENT_GROUPS 1
#endif

#endif /* FREERTOS_H */
