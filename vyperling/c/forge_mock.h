/* forge_mock.h — vyperling mock runtime (shared, vendored).
 *
 * Generic machinery used by every generated mock_<module>.c:
 *   - a no-heap bump-allocator arena (works bare-metal under QEMU)
 *   - a refcounted acquire/release so multiple modules can share the arena
 *     within one test without one module's Init wiping another's queue
 *   - a generic FIFO queue of call-instance records
 *   - a failure funnel that routes every mock failure through Unity
 *
 * Generated mocks #include this. Do not edit generated code; edit here.
 */
#ifndef FORGE_MOCK_H
#define FORGE_MOCK_H

#include <stddef.h>
#include "unity.h"

/* Size of the static arena. Override with -DFORGE_MOCK_MEM_SIZE=... if a test
 * queues enough expectations to exhaust it. */
#ifndef FORGE_MOCK_MEM_SIZE
#define FORGE_MOCK_MEM_SIZE 32768
#endif

/* ---- Arena (bump allocator, no heap) ------------------------------------ */

/* Refcounted. The arena is reset only on the FIRST acquire of a round, so
 * every mock_<mod>_Init() in setUp() shares one arena cleanly. */
void  forge_mock_arena_acquire(void);
void  forge_mock_arena_release(void);
void *forge_mock_alloc(size_t size);  /* aligned; fails the test on OOM */

/* ---- Generic FIFO queue of call-instance records ------------------------
 * Each record's FIRST member must be a `void *next` link. Generated per-
 * function structs follow that layout. */
typedef struct forge_mock_queue_s {
    void *head;      /* oldest queued expectation */
    void *tail;      /* newest */
    void *replay;    /* next record to consume on an actual call */
    int   count;     /* total queued */
    int   consumed;  /* calls replayed so far */
} forge_mock_queue;

void  forge_mock_queue_reset(forge_mock_queue *q);
void *forge_mock_queue_push(forge_mock_queue *q, size_t size); /* alloc+append */
void *forge_mock_queue_pop(forge_mock_queue *q);               /* current or NULL */

/* ---- Failure funnel — everything routes through Unity ------------------- */

void forge_mock_set_line(int line);                            /* line of the Expect call */
void forge_mock_fail(const char *func, const char *msg);       /* -> UNITY_TEST_FAIL */
void forge_mock_fail_no_expect(const char *func);              /* called more than expected */
void forge_mock_verify_queue(const char *func, forge_mock_queue *q); /* too-few-calls */

#endif /* FORGE_MOCK_H */
