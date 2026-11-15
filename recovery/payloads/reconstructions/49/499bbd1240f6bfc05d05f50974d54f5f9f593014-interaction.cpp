#include "interaction.h"

#include <creatures/players/player.h>

#include <view/gamescene.h>
#include <view/gameview.h>

#include <view/playerstatsview.h>
#include <view/fightview.h>

#include <items/armors/armor.h>
#include <QDebug>

#include <interactions/attacks/attack.h>
#include <interactions/attacks/elemstaff.h>
#include <interactions/skills/doubleattack.h>
#include <interactions/skills/sneakattack.h>
#include <interactions/skills/strike.h>
#include <interactions/skills/stunner.h>
#include <interactions/spells/chaosblast.h>
#include <interactions/spells/frostbolt.h>
#include <interactions/spells/magicmissile.h>

std::list<Interaction*> Interaction::actions;

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

int Interaction::getManaCost()
{
    return manaCost;
}

void Interaction::setAnimation(std::string path)
{
    ListItem::setAnimation(path);
}

void Interaction::mousePressEvent(QGraphicsSceneMouseEvent *event)
{
    Player *player=GameScene::getPlayer();
    if(player->getFightList()->size()==0)return;
    if(manaCost>player->getMana())return;
    Creature *creature=FightView::selected;
    if(!creature)return;
    action(player,creature);
    player->takeMana(manaCost);

    Armor *armor=creature->getArmor();
    if(armor)
    {
        Interaction *interaction=armor->getInteraction();
        if(interaction)interaction->action(creature,player);
    }

    if(!creature->isAlive())
    {
        qDebug()<<player->className.c_str()<<"defeated"<<creature->className.c_str()<<"\n";
        player->addExpScaled(creature->getScale());
        player->addItem(creature->getLoot());
        creature->removeFromGame();
        player->getFightList()->remove(creature);
        if(player->getFightList()->size()==0)
        {
            GameScene::getView()->getFightView()->setVisible(false);
            FightView::selected=0;
        }
        else
        {
            FightView::selected=player->getFightList()->front();
        }
        player->getStatsView()->update();
    } else
    {
        qDebug()<<"";
        for(std::list<Creature*>::iterator it=player->getFightList()->begin();
                it!=player->getFightList()->end(); it++)
        {
            (*it)->fight(player);
        }
    }
    GameScene::getView()->getFightView()->update();
    if(!player->isAlive()) {
        GameScene::getView()->close();
    }
}

Interaction *Interaction::getAction(std::string name)
{
    if(actions.size()==0)init();
    for(std::list<Interaction*>::iterator it=actions.begin(); it!=actions.end(); it++)
    {
        if((*it)->className==name)return (*it)->clone();
    }
    return 0;
}

void Interaction::terminate()
{
    for(std::list<Interaction*>::iterator it=actions.begin(); it!=actions.end(); it++)
    {
        delete *it;
    }
    actions.clear();
}

void Interaction::init()
{
    actions.push_back(new Attack());
    actions.push_back(new ElemStaff());
    actions.push_back(new DoubleAttack());
    actions.push_back(new SneakAttack());
    actions.push_back(new Strike());
    actions.push_back(new Stunner());
    actions.push_back(new ChaosBlast());
    actions.push_back(new FrostBolt());
    actions.push_back(new MagicMissile());
}
