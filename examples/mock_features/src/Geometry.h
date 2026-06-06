#ifndef GEOMETRY_H
#define GEOMETRY_H

/* Struct-by-value parameters.
 *
 * Complete structs (members visible) are captured & byte-compared by the mock
 * via UNITY_TEST_ASSERT_EQUAL_MEMORY — sizeof is known.
 *
 * Incomplete (opaque) structs — forward-declared only, sizeof unknown — cannot
 * be stored or compared, so functions taking one by value are SKIPPED with a
 * warning. A pointer to the same opaque struct is fine (sizeof is pointer-size).
 */

struct Point {
    int x;
    int y;
};

typedef struct {
    int width;
    int height;
} Size;

/* opaque — defined elsewhere, body not visible here */
struct Opaque;

int classify_point(struct Point p);
int area(Size s);

/* SKIPPED by mockgen: opaque struct by value */
void use_opaque(struct Opaque o);

/* NOT skipped: pointer to opaque is just a pointer */
void use_opaque_ptr(struct Opaque *o);

#endif /* GEOMETRY_H */
