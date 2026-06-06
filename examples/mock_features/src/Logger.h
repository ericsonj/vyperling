#ifndef LOGGER_H
#define LOGGER_H

/* Variadic functions — fixed params are captured & asserted by the mock;
 * the variadic tail is ignored (a va_list cannot be inspected after the call). */

int  log_printf(const char *fmt, ...);
void log_event(int code, ...);

#endif /* LOGGER_H */
