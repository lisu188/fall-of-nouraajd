#ifndef BOOTS_H
#define BOOTS_H
#include "item.h"

class Boots : public Item
{
    Q_OBJECT
public:
    Boots();
    Boots(const Boots& boots);
};
Q_DECLARE_METATYPE(Boots)
#endif // BOOTS_H
