#include "Geometry.h"

struct Opaque {
    int secret;
};

int classify_point(struct Point p)
{
    if (p.x == 0 && p.y == 0) {
        return 0; /* origin */
    }
    return (p.x >= 0 && p.y >= 0) ? 1 : -1;
}

int area(Size s)
{
    return s.width * s.height;
}

void use_opaque(struct Opaque o)
{
    (void)o;
}

void use_opaque_ptr(struct Opaque *o)
{
    (void)o;
}
