#include "parser.h"

#include <ctype.h>
#include <stddef.h>

int parser_token_count(const char *line)
{
    int count = 0;
    int in_token = 0;

    if (line == NULL) {
        return 0;
    }

    for (; *line != '\0'; line++) {
        if (isspace((unsigned char)*line)) {
            in_token = 0;
        } else if (!in_token) {
            in_token = 1;
            count++;
        }
    }

    return count;
}

#ifdef PARSER_DEBUG
void parser_dump_state(const char *line, int token_count)
{
    /* Real builds print to stderr; the mock for this function just records
     * the call so tests can assert it fired with the right arguments. */
    (void)line;
    (void)token_count;
}
#endif
