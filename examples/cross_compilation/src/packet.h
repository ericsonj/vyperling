#ifndef PACKET_H
#define PACKET_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#include "crc16.h"

/*
 * Framing: [SOF 0xAA][len 1B][payload len B][CRC16 2B BE]
 *
 * packet_validate() verifies SOF, declared length vs buffer, and CRC over
 * payload bytes only. Depends on crc16_compute() — mocked in tests.
 */

#define PACKET_SOF      0xAAu
#define PACKET_HDR_SIZE 2u   /* SOF + len */
#define PACKET_CRC_SIZE 2u
#define PACKET_MIN_SIZE (PACKET_HDR_SIZE + PACKET_CRC_SIZE)

typedef struct {
    const uint8_t *buf;
    size_t         buf_len;
} Packet;

bool packet_validate(const Packet *pkt);

#endif /* PACKET_H */
