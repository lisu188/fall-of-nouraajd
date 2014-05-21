#include "item.h"

#ifndef BELT_H
#define BELT_H

class Belt : public Item
{
    Q_OBJECT
public:
    Belt();
    Belt(const Belt& belt);
};
Q_DECLARE_METATYPE(Belt)
#endif // BELT_H
