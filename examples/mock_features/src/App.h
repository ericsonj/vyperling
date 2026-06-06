#ifndef APP_H
#define APP_H

#include "Geometry.h"

/* System-under-test. Depends on Logger (variadic), EventBus (fnptr params),
 * and Geometry (struct-by-value). Its tests mock those three dependencies and
 * assert App calls them with the right arguments. */

void app_on_tick(int code);
int  app_score(struct Point p);
void app_install_handler(void (*handler)(int));

#endif /* APP_H */
