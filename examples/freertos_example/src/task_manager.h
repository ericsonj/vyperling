#ifndef TASK_MANAGER_H
#define TASK_MANAGER_H

#include "FreeRTOS.h"
#include "task.h"

#define TASK_MANAGER_STACK_DEPTH 256
#define TASK_MGR_PRODUCER_PRIORITY (tskIDLE_PRIORITY + 2)
#define TASK_MGR_CONSUMER_PRIORITY (tskIDLE_PRIORITY + 1)

typedef enum {
    TASK_MGR_OK = 0,
    TASK_MGR_ERR_CREATE_FAILED,
} TaskMgrStatus;

TaskMgrStatus task_manager_init(void);
void task_manager_run(void);

#endif /* TASK_MANAGER_H */
