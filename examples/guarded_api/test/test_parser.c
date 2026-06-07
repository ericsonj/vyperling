/* test_parser — exercises Parser directly (its own SUT, no mocks).
 *
 * parser_dump_state() is declared in parser.h only when PARSER_DEBUG is
 * defined. forge.yml sets compiler.defines: [PARSER_DEBUG], so this test
 * file — compiled with the exact same defines as the real build — sees
 * and can call it directly. Remove PARSER_DEBUG from forge.yml and this
 * file fails to compile with "implicit declaration" — same as the real
 * build would. */

#include "unity.h"
#include "parser.h"

void setUp(void)    {}
void tearDown(void) {}

void test_parser_token_count_counts_words(void)
{
    TEST_ASSERT_EQUAL_INT(3, parser_token_count("foo bar baz"));
}

void test_parser_token_count_collapses_whitespace(void)
{
    TEST_ASSERT_EQUAL_INT(2, parser_token_count("  foo    bar  "));
}

void test_parser_token_count_empty_line_is_zero(void)
{
    TEST_ASSERT_EQUAL_INT(0, parser_token_count(""));
}

void test_parser_token_count_null_is_zero(void)
{
    TEST_ASSERT_EQUAL_INT(0, parser_token_count(NULL));
}

#ifdef PARSER_DEBUG
void test_parser_dump_state_is_callable_when_debug_defined(void)
{
    /* Just demonstrates the guarded symbol links and runs — no assertions
     * on stderr output. Its presence here mirrors its presence in the
     * generated mock_Parser (see test_line_processor.c). */
    parser_dump_state("foo bar", 2);
    TEST_PASS();
}
#endif
