#include "Logger.h"
#include <stdarg.h>
#include <stdio.h>

int log_printf(const char *fmt, ...)
{
    va_list ap;
    int n;
    va_start(ap, fmt);
    n = vprintf(fmt, ap);
    va_end(ap);
    return n;
}

void log_event(int code, ...)
{
    (void)code;
}
