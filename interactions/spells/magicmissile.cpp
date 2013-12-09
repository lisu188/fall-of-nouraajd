#include "magicmissile.h"

MagicMissile::MagicMissile()
{
    className="MagicMissile";
    manaCost=5;
    setAnimation("images/spells/magicmissile/");
}

void MagicMissile::action(Creature *first, Creature *second)
{
    Interaction::action(first,second);
    int dmg=0;
    for(int i=0; i<first->getMana()/10+1; i++)
    {
        dmg+=rand()%4+1;
    }
    second->hurt(dmg);
}

Interaction *MagicMissile::clone()
{
    return new MagicMissile();
}
