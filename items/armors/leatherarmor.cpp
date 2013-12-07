#include "leatherarmor.h"

LeatherArmor::LeatherArmor()
{
    className="LeatherArmor";
    setAnimation("images/items/armors/leatherarmor/");
    bonus->setAgility(5);
    bonus->setStamina(2);
    bonus->setCrit(2);
}
