#include "validator.h"

#include <string.h>

void validator_check(const char *line)
{
    size_t len;

    if (line == NULL || line[0] == '\0') {
        Throw(VALIDATOR_ERR_EMPTY);
    }

    len = strlen(line);
    if (len > VALIDATOR_MAX_LEN) {
        Throw(VALIDATOR_ERR_TOO_LONG);
    }
}
