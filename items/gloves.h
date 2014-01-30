#ifndef GLOVES_H
#define GLOVES_H
#include "item.h"

class Gloves : public Item
{
    Q_OBJECT
public:
    Gloves();
    Gloves(const Gloves& gloves);
};
Q_DECLARE_METATYPE(Gloves)
#endif // GLOVES_H
