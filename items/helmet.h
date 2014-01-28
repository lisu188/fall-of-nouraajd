#include "item.h"

#ifndef HELMET_H
#define HELMET_H

class Helmet : public Item
{
public:
    Helmet();
    Helmet(const Helmet &helmet);
};
Q_DECLARE_METATYPE(Helmet)
#endif // HELMET_H
