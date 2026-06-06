#ifndef EVENT_BUS_H
#define EVENT_BUS_H

/* Function-pointer parameters — the callback pointer is stored as void* in the
 * mock and asserted by identity (UNITY_TEST_ASSERT_EQUAL_PTR): "was the right
 * callback passed?".
 *
 * Note: the params are written in raw form `void (*cb)(int)` rather than via a
 * typedef. mockgen detects the raw PtrDecl->FuncDecl shape; a typedef'd fnptr
 * (`my_cb_t cb`) renders as a plain identifier and falls through to MEMORY
 * compare instead. */

void register_cb(void (*cb)(int));
int  transform(int (*fn)(int, int), int x, int y);

#endif /* EVENT_BUS_H */
