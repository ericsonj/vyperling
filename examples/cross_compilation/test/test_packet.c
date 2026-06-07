#include "unity.h"
#include "mock_crc16.h"
#include "packet.h"

void setUp(void)    { mock_crc16_Init(); }
void tearDown(void) { mock_crc16_Verify(); mock_crc16_Destroy(); }

/* Helper — build a minimal valid packet buffer in caller's stack array. */
static void _build_packet(uint8_t *buf, uint8_t payload_len,
                           const uint8_t *payload, uint16_t crc) {
    buf[0] = PACKET_SOF;
    buf[1] = payload_len;
    for (uint8_t i = 0; i < payload_len; i++)
        buf[PACKET_HDR_SIZE + i] = payload[i];
    buf[PACKET_HDR_SIZE + payload_len]     = (uint8_t)(crc >> 8);
    buf[PACKET_HDR_SIZE + payload_len + 1] = (uint8_t)(crc & 0xFF);
}

void test_null_packet_returns_false(void) {
    TEST_ASSERT_FALSE(packet_validate(NULL));
}

void test_null_buf_returns_false(void) {
    Packet pkt = {.buf = NULL, .buf_len = 4};
    TEST_ASSERT_FALSE(packet_validate(&pkt));
}

void test_too_short_returns_false(void) {
    uint8_t buf[3] = {PACKET_SOF, 0x00, 0x00};
    Packet pkt = {.buf = buf, .buf_len = 3};
    TEST_ASSERT_FALSE(packet_validate(&pkt));
}

void test_bad_sof_returns_false(void) {
    uint8_t buf[4] = {0xBB, 0x00, 0xFF, 0xFF};
    Packet pkt = {.buf = buf, .buf_len = 4};
    TEST_ASSERT_FALSE(packet_validate(&pkt));
}

void test_valid_empty_payload(void) {
    /* payload_len=0, so CRC covers zero bytes */
    uint8_t buf[4];
    _build_packet(buf, 0, NULL, 0xABCD);

    crc16_compute_ExpectAndReturn(buf + PACKET_HDR_SIZE, 0, 0xABCD);

    Packet pkt = {.buf = buf, .buf_len = sizeof(buf)};
    TEST_ASSERT_TRUE(packet_validate(&pkt));
}

void test_valid_packet_with_payload(void) {
    const uint8_t payload[] = {0x01, 0x02, 0x03};
    uint8_t buf[PACKET_HDR_SIZE + sizeof(payload) + PACKET_CRC_SIZE];
    _build_packet(buf, sizeof(payload), payload, 0x1234);

    crc16_compute_ExpectAndReturn(
        buf + PACKET_HDR_SIZE, sizeof(payload), 0x1234
    );

    Packet pkt = {.buf = buf, .buf_len = sizeof(buf)};
    TEST_ASSERT_TRUE(packet_validate(&pkt));
}

void test_crc_mismatch_returns_false(void) {
    const uint8_t payload[] = {0xFF};
    uint8_t buf[PACKET_HDR_SIZE + sizeof(payload) + PACKET_CRC_SIZE];
    _build_packet(buf, sizeof(payload), payload, 0x1111);

    /* mock returns a different CRC → validation must fail */
    crc16_compute_ExpectAndReturn(
        buf + PACKET_HDR_SIZE, sizeof(payload), 0x2222
    );

    Packet pkt = {.buf = buf, .buf_len = sizeof(buf)};
    TEST_ASSERT_FALSE(packet_validate(&pkt));
}

void test_declared_len_exceeds_buffer_returns_false(void) {
    /* buf_len too small for the declared payload */
    uint8_t buf[4] = {PACKET_SOF, 0x10, 0x00, 0x00}; /* payload_len=16 but only 4 bytes */
    Packet pkt = {.buf = buf, .buf_len = sizeof(buf)};
    /* crc16_compute must NOT be called — no mock expectation set */
    TEST_ASSERT_FALSE(packet_validate(&pkt));
}
