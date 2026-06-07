#include "line_processor.h"

#include "CException.h"
#include "parser.h"
#include "validator.h"

int line_processor_handle(const char *line)
{
    CEXCEPTION_T e;
    int count;

    Try {
        validator_check(line);
    } Catch(e) {
        (void)e;
        return -1;
    }

    count = parser_token_count(line);

#ifdef PARSER_DEBUG
    parser_dump_state(line, count);
#endif

    return count;
}
