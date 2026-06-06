#include "App.h"
#include "Logger.h"
#include "EventBus.h"

void app_on_tick(int code)
{
    /* variadic dependency call */
    log_printf("tick: %d", code);
}

int app_score(struct Point p)
{
    /* struct-by-value dependency call */
    int kind = classify_point(p);
    log_printf("score", kind);
    return kind;
}

void app_install_handler(void (*handler)(int))
{
    /* fnptr-param dependency call */
    register_cb(handler);
}
