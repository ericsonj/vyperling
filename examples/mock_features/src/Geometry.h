#ifndef GEOMETRY_H
#define GEOMETRY_H

/* Struct-by-value parameters.
 *
 * Complete structs (members visible) are captured & byte-compared by the mock
 * via UNITY_TEST_ASSERT_EQUAL_MEMORY — sizeof is known.
 *
 * Pointer-to-opaque is fine — sizeof is pointer-size regardless of the
 * struct body. use_opaque_ptr() demonstrates this case. */

struct Point {
    int x;
    int y;
};

typedef struct {
    int width;
    int height;
} Size;

/* opaque — body not visible in this header; typedef'd so CMock can treat as PTR */
struct Opaque;
typedef struct Opaque Opaque_t;

int classify_point(struct Point p);
int area(Size s);

/* pointer to opaque — mockable (pointer has known size) */
void use_opaque_ptr(Opaque_t *o);

#endif /* GEOMETRY_H */
