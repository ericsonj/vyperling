#include "EventBus.h"

static void (*g_cb)(int) = 0;

void register_cb(void (*cb)(int))
{
    g_cb = cb;
}

int transform(int (*fn)(int, int), int x, int y)
{
    return fn(x, y);
}
