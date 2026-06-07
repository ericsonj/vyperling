#ifndef LINE_PROCESSOR_H
#define LINE_PROCESSOR_H

/* Returns the token count for a valid line, or -1 if validator_check()
 * Threw (any CException error). Demonstrates Try/Catch around a mocked
 * dependency from the SUT side. */
int line_processor_handle(const char *line);

#endif /* LINE_PROCESSOR_H */
