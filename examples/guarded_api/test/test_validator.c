/* test_validator — exercises Validator directly (no mocks). Demonstrates
 * vyperling's CException support: vendored CException.c/.h are linked into
 * the test binary because forge.yml sets compiler.cexception: true, so
 * Try/Catch/Throw/CEXCEPTION_T are available exactly as in the real build. */

#include "unity.h"
#include "CException.h"
#include "validator.h"

void setUp(void)    {}
void tearDown(void) {}

void test_validator_check_accepts_normal_line(void)
{
    CEXCEPTION_T e = CEXCEPTION_NONE;

    Try {
        validator_check("hello world");
    } Catch(e) {
        TEST_FAIL_MESSAGE("validator_check threw on a valid line");
    }

    TEST_ASSERT_EQUAL_UINT(CEXCEPTION_NONE, e);
}

void test_validator_check_throws_on_empty_line(void)
{
    CEXCEPTION_T e = CEXCEPTION_NONE;

    Try {
        validator_check("");
        TEST_FAIL_MESSAGE("expected VALIDATOR_ERR_EMPTY to be thrown");
    } Catch(e) {
        TEST_ASSERT_EQUAL_UINT(VALIDATOR_ERR_EMPTY, e);
    }
}

void test_validator_check_throws_on_null_line(void)
{
    CEXCEPTION_T e = CEXCEPTION_NONE;

    Try {
        validator_check(NULL);
        TEST_FAIL_MESSAGE("expected VALIDATOR_ERR_EMPTY to be thrown for NULL");
    } Catch(e) {
        TEST_ASSERT_EQUAL_UINT(VALIDATOR_ERR_EMPTY, e);
    }
}

void test_validator_check_throws_on_too_long_line(void)
{
    CEXCEPTION_T e = CEXCEPTION_NONE;
    /* 33 'x' chars — one over VALIDATOR_MAX_LEN (32) */
    const char *too_long = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx";

    Try {
        validator_check(too_long);
        TEST_FAIL_MESSAGE("expected VALIDATOR_ERR_TOO_LONG to be thrown");
    } Catch(e) {
        TEST_ASSERT_EQUAL_UINT(VALIDATOR_ERR_TOO_LONG, e);
    }
}
