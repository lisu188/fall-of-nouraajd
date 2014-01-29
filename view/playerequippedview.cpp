#include "playerequippedview.h"

#include <items/item.h>

PlayerEquippedView::PlayerEquippedView(std::map<int, Item *> *equipped):equipped(equipped)
{
    for(int i=0; i<equipped->size(); i++)
    {
    }
}
