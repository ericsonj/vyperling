# freertos_example

Unit-testing FreeRTOS application code with vyperling on ARM Cortex-M4F.

## What this shows

| Module | FreeRTOS APIs covered |
|---|---|
| `task_manager` | `xTaskCreate`, `vTaskStartScheduler`, `vTaskDelay` |
| `queue_buffer` | `xQueueCreate` → `xQueueGenericCreate`, `xQueueSend`, `xQueueReceive` |
| `semaphore_guard` | `xSemaphoreCreateBinary`, `xSemaphoreCreateMutex`, `xSemaphoreTake`, `xSemaphoreGive` |
| `event_flags` | `xEventGroupCreate`, `xEventGroupSetBits`, `xEventGroupWaitBits` |
| `timer_blink` | `xTimerCreate`, `xTimerStart`/`xTimerStop` → `xTimerGenericCommand` |

## Key design choice: stub headers

The `include/freertos/` directory contains minimal stub headers that reproduce
the exact function signatures from the real FreeRTOS headers. These stubs:

- Declare the **underlying real functions** that public macros expand to
  (e.g. `xQueueGenericCreate` rather than the `xQueueCreate` macro)
- Are parseable by pycparser without the full FreeRTOS source tree
- Work with both native GCC and arm-none-eabi-gcc

Do NOT mock `semphr.h` — it is entirely macros. Mock `queue.h` instead;
test code using `xSemaphoreXxx` macros expands transparently to the mocked
underlying functions at preprocessor time.

## Running

```bash
# Install vyperling (once)
pip install -e ../..

# Generate mocks from stub headers
vpl mock include/freertos/task.h
vpl mock include/freertos/queue.h
vpl mock include/freertos/event_groups.h
vpl mock include/freertos/timers.h

# Run all tests (native target, no toolchain install needed)
vpl test

# Run on ARM Cortex-M4 via QEMU (requires arm-none-eabi-gcc + qemu-arm)
vpl test --target arm-cortex-m4
```

## ARM Cortex-M4F hard-float

Uncomment the `extra_cflags` block in `forge.yml` to enable the FPU:

```yaml
extra_cflags:
  - -mfpu=fpv4-sp-d16
  - -mfloat-abi=hard
```

The builtin `arm-cortex-m4` toolchain already passes `-mcpu=cortex-m4 -mthumb`.
