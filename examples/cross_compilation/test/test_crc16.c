#include "unity.h"
#include "crc16.h"

void setUp(void)    {}
void tearDown(void) {}

/* Known-good vectors from https://crccalc.com (CRC-16/CCITT-FALSE). */

void test_empty_input_returns_init_value(void) {
    TEST_ASSERT_EQUAL_HEX16(0xFFFF, crc16_compute(NULL, 0));
}

void test_single_zero_byte(void) {
    uint8_t data[] = {0x00};
    /* 0xFFFF XOR (0x00<<8) = 0xFF00, then 8 iterations: known result 0xE1F0 */
    TEST_ASSERT_EQUAL_HEX16(0xE1F0, crc16_compute(data, 1));
}

void test_known_vector_123456789(void) {
    /* "123456789" → CRC-16/CCITT-FALSE = 0x29B1 */
    const uint8_t data[] = {'1','2','3','4','5','6','7','8','9'};
    TEST_ASSERT_EQUAL_HEX16(0x29B1, crc16_compute(data, sizeof(data)));
}

void test_incremental_equals_bulk(void) {
    const uint8_t data[] = {0xDE, 0xAD, 0xBE, 0xEF};
    uint16_t bulk = crc16_compute(data, sizeof(data));

    uint16_t inc = 0xFFFF;
    for (size_t i = 0; i < sizeof(data); i++)
        inc = crc16_update(inc, data[i]);

    TEST_ASSERT_EQUAL_HEX16(bulk, inc);
}

void test_different_data_gives_different_crc(void) {
    const uint8_t a[] = {0x01};
    const uint8_t b[] = {0x02};
    TEST_ASSERT_NOT_EQUAL(crc16_compute(a, 1), crc16_compute(b, 1));
}
