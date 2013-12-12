#include "interaction.h"

#include <creatures/player.h>

#include <view/gamescene.h>
#include <view/gameview.h>

#include <view/playerstatsview.h>
#include <view/fightview.h>

#include <items/armors/armor.h>
#include <QDebug>


#include <interactions/skills/doubleattack.h>
#include <interactions/skills/sneakattack.h>
#include <interactions/skills/strike.h>
#include <interactions/skills/stunner.h>

#include <interactions/spells/abyssalshadows.h>
#include <interactions/spells/chaosblast.h>
#include <interactions/spells/devour.h>
#include <interactions/spells/endlesspain.h>
#include <interactions/spells/frostbolt.h>
#include <interactions/spells/magicmissile.h>
#include <interactions/spells/shadowbolt.h>

#include <interactions/attacks/attack.h>
#include <interactions/attacks/elemstaff.h>
#include <list>
#include <creatures/creature.h>


Interaction::Interaction()
{
    className="Interaction";
    manaCost=0;
}

Interaction::~Interaction()
{
}

void Interaction::action(Creature *first, Creature *second)
{
    qDebug() << first->className.c_str() << " used "
             << this->className.c_str() << " against "
             << second->className.c_str();
}

int Interaction::getManaCost() {
    return manaCost;
}

void Interaction::setAnimation(std::string path)
{
    ListItem::setAnimation(path);
}

void Interaction::mousePressEvent(QGraphicsSceneMouseEvent *event)
{
    Player *player=GameScene::getPlayer();
    if(player->getFightList()->size()==0) {
        return;
    }
    if(manaCost>player->getMana()) {
        return;
    }
    Creature *creature=FightView::selected;
    if(!creature) {
        return;
    }
    player->performAction(this,creature);
}

Interaction *Interaction::getAction(std::string name)
{
    if(name.compare("")==0) {
        return 0;
    }
    if(name.compare("Attack")==0)
    {
        return new Attack();
    } else if(name.compare("DoubleAttack")==0)
    {
        return new DoubleAttack();
    } else if(name.compare("SneakAttack")==0)
    {
        return new SneakAttack();
    } else if(name.compare("Strike")==0)
    {
        return new Strike();
    } else if(name.compare("Stunner")==0)
    {
        return new Stunner();
    } else if(name.compare("ChaosBlast")==0)
    {
        return new ChaosBlast();
    } else if(name.compare("FrostBolt")==0)
    {
        return new FrostBolt();
    } else if(name.compare("MagicMissile")==0)
    {
        return new MagicMissile();
    } else if(name.compare("ElemStaff")==0)
    {
        return new ElemStaff();
    }
    else if(name.compare("AbyssalShadows")==0)
    {
        return new AbyssalShadows();
    }
    else if(name.compare("EndlessPain")==0)
    {
        return new EndlessPain();
    }
    else if(name.compare("ShadowBolt")==0)
    {
        return new ShadowBolt();
    }
    else if(name.compare("Devour")==0)
    {
        return new Devour();
    }
    return 0;
}

