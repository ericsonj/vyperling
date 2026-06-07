#include "packet.h"

bool packet_validate(const Packet *pkt) {
    if (!pkt || !pkt->buf || pkt->buf_len < PACKET_MIN_SIZE)
        return false;
    if (pkt->buf[0] != PACKET_SOF)
        return false;

    uint8_t payload_len = pkt->buf[1];
    size_t  total = PACKET_HDR_SIZE + payload_len + PACKET_CRC_SIZE;
    if (pkt->buf_len < total)
        return false;

    uint16_t computed = crc16_compute(pkt->buf + PACKET_HDR_SIZE, payload_len);
    uint16_t stored   = ((uint16_t)pkt->buf[PACKET_HDR_SIZE + payload_len] << 8)
                      |  (uint16_t)pkt->buf[PACKET_HDR_SIZE + payload_len + 1];
    return computed == stored;
}
