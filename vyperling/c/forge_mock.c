/* forge_mock.c — vyperling mock runtime (shared, vendored). See forge_mock.h. */
#include "forge_mock.h"
#include "unity.h"

static unsigned char forge_mock_arena[FORGE_MOCK_MEM_SIZE];
static size_t        forge_mock_used = 0;
static int           forge_mock_refs = 0;
static int           forge_mock_line = 0;

#define FORGE_MOCK_ALIGN (sizeof(void *))

void forge_mock_arena_acquire(void)
{
    if (forge_mock_refs == 0) {
        forge_mock_used = 0;  /* reset only at the start of a round */
    }
    forge_mock_refs++;
}

void forge_mock_arena_release(void)
{
    if (forge_mock_refs > 0) {
        forge_mock_refs--;
    }
}

void *forge_mock_alloc(size_t size)
{
    size = (size + (FORGE_MOCK_ALIGN - 1)) & ~(FORGE_MOCK_ALIGN - 1);
    if (forge_mock_used + size > FORGE_MOCK_MEM_SIZE) {
        UNITY_TEST_FAIL((UNITY_LINE_TYPE)forge_mock_line,
                        "forge_mock: arena exhausted; raise FORGE_MOCK_MEM_SIZE");
        return 0;
    }
    {
        void *p = &forge_mock_arena[forge_mock_used];
        forge_mock_used += size;
        return p;
    }
}

void forge_mock_queue_reset(forge_mock_queue *q)
{
    q->head = q->tail = q->replay = 0;
    q->count = 0;
    q->consumed = 0;
}

void *forge_mock_queue_push(forge_mock_queue *q, size_t size)
{
    void *rec = forge_mock_alloc(size);
    if (!rec) {
        return 0;
    }
    *(void **)rec = 0;  /* next = NULL */
    if (q->tail) {
        *(void **)q->tail = rec;
        /* If replay is NULL all previously pushed items were consumed; restart
         * the replay cursor so the new item can be popped. */
        if (!q->replay) {
            q->replay = rec;
        }
    } else {
        q->head = rec;
        q->replay = rec;
    }
    q->tail = rec;
    q->count++;
    return rec;
}

void *forge_mock_queue_pop(forge_mock_queue *q)
{
    void *rec = q->replay;
    if (rec) {
        q->replay = *(void **)rec;
        q->consumed++;
    }
    return rec;
}

void forge_mock_set_line(int line)
{
    forge_mock_line = line;
}

/* Build "<func>: <msg>" without depending on sprintf/stdio. */
void forge_mock_fail(const char *func, const char *msg)
{
    static char buf[256];
    size_t i = 0;
    const char *s = func;
    while (*s && i < 200) {
        buf[i++] = *s++;
    }
    buf[i++] = ':';
    buf[i++] = ' ';
    s = msg;
    while (*s && i < 255) {
        buf[i++] = *s++;
    }
    buf[i] = 0;
    UNITY_TEST_FAIL((UNITY_LINE_TYPE)forge_mock_line, buf);
}

void forge_mock_fail_no_expect(const char *func)
{
    forge_mock_fail(func, "called more times than expected");
}

void forge_mock_verify_queue(const char *func, forge_mock_queue *q)
{
    if (q->consumed < q->count) {
        forge_mock_fail(func, "expected call(s) not received before Verify");
    }
}
