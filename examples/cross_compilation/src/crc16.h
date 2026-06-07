#ifndef CRC16_H
#define CRC16_H

#include <stdint.h>
#include <stddef.h>

/* CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflection). */

uint16_t crc16_update(uint16_t crc, uint8_t byte);
uint16_t crc16_compute(const uint8_t *data, size_t len);

#endif /* CRC16_H */
