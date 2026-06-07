/* test_line_processor — LineProcessor is the SUT; Parser is mocked.
 *
 * Validator is NOT mocked here on purpose: validator_check() communicates
 * failure by Throw()ing a CEXCEPTION_T, and a generated mock cannot
 * replicate a non-local jump — it can only Expect/Return. Exercising the
 * real Validator keeps the Try/Catch path in LineProcessor genuinely
 * under test (see CException support, demonstrated end-to-end here).
 *
 * Parser IS mocked — and mock_parser_*_Expect for parser_dump_state proves
 * mockgen saw the #ifdef PARSER_DEBUG-guarded declaration: forge.yml's
 * compiler.defines: [PARSER_DEBUG] is forwarded to the same `cc -E` pass
 * mockgen uses, so the guarded symbol appears in the generated mock API
 * exactly as it appears in the real compiled Parser.
 *
 * validator.c is linked here as a real source (not mocked — see above).
 * vyperling: declared once in forge.yml under project.extra_srcs.line_processor.
 * Ceedling:  declared per-test via the TEST_SOURCE_FILE build-directive macro
 *            after the includes below — both are the respective tool's
 *            documented mechanism for "link this real collaborator
 *            alongside this one test executable". TEST_SOURCE_FILE expands
 *            to nothing (see unity.h) — it is a build directive Ceedling's
 *            preprocessor scans for as plain text, not a runtime call.
 */

#include "unity.h"
#include "line_processor.h"
#include "mock_parser.h"

TEST_SOURCE_FILE("validator.c")

void setUp(void)
{
    mock_parser_Init();
}

void tearDown(void)
{
    mock_parser_Verify();
    mock_parser_Destroy();
}

void test_line_processor_handle_returns_token_count_for_valid_line(void)
{
    parser_token_count_ExpectAndReturn("two words", 2);
#ifdef PARSER_DEBUG
    /* Generated only because mockgen resolved the #ifdef guard the same
     * way the real compile does — proof the guard was honoured. */
    parser_dump_state_Expect("two words", 2);
#endif

    TEST_ASSERT_EQUAL_INT(2, line_processor_handle("two words"));
}

void test_line_processor_handle_returns_minus_one_on_empty_line(void)
{
    /* validator_check() Throws before Parser is ever consulted —
     * no Parser mock expectations are set. */
    TEST_ASSERT_EQUAL_INT(-1, line_processor_handle(""));
}

void test_line_processor_handle_returns_minus_one_on_too_long_line(void)
{
    const char *too_long = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx";

    TEST_ASSERT_EQUAL_INT(-1, line_processor_handle(too_long));
}
