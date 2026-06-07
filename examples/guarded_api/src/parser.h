#ifndef PARSER_H
#define PARSER_H

/* Always-visible API. */
int parser_token_count(const char *line);

/* Guarded by a project-wide define (compiler.defines: [PARSER_DEBUG] in
 * forge.yml). vyperling's mockgen runs the header through the *real*
 * preprocessor (cc -E) using the same defines as the compile step, so this
 * declaration is visible to mockgen and a mock_parser_dump_state symbol is
 * generated — exactly mirroring what the real compile sees. Removing
 * PARSER_DEBUG from forge.yml's compiler.defines makes both the real build
 * and the generated mock drop this function together. */
#ifdef PARSER_DEBUG
void parser_dump_state(const char *line, int token_count);
#endif

#endif /* PARSER_H */
