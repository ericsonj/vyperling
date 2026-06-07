#ifndef VALIDATOR_H
#define VALIDATOR_H

#include "CException.h"

/* Error codes Thrown by validator_check(). CEXCEPTION_T defaults to
 * `unsigned int` (see CException.h) — plain ints fit it directly. */
#define VALIDATOR_ERR_EMPTY      1u
#define VALIDATOR_ERR_TOO_LONG   2u

#define VALIDATOR_MAX_LEN        32

/* Throws VALIDATOR_ERR_EMPTY / VALIDATOR_ERR_TOO_LONG via CEXCEPTION_T —
 * never returns an error code. Callers wrap it in Try/Catch. */
void validator_check(const char *line);

#endif /* VALIDATOR_H */
