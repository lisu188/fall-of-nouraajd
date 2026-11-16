#include "interaction.h"

#include <creatures/player.h>

#include <view/gamescene.h>
#include <view/gameview.h>

#include <view/playerstatsview.h>
#include <view/fightview.h>

#include <items/armor.h>
#include <items/weapon.h>
#include <stats/stats.h>
#include <stats/damage.h>
#include <configuration/configurationprovider.h>

#include <effects/effect.h>

#include <QDebug>
#include <list>
#include <creatures/creature.h>

std::unordered_map<std::string,std::function<void (Creature *, Creature *)>> Interaction::actions= {
    {"Attack",Attack},
    {"ElemStaff",ElemStaff},
    {"DoubleAttack",DoubleAttack},
    {"SneakAttack",SneakAttack},
    {"Strike",Strike},
    {"Stunner",Stunner},
    {"AbyssalShadows",AbyssalShadows},
    {"ArmorOfEndlessWinter",ArmorOfEndlessWinter},
    {"ChaosBlast",ChaosBlast},
    {"Devour",Devour},
    {"EndlessPain",EndlessPain},
    {"FrostBolt",FrostBolt},
    {"MagicMissile",MagicMissile},
    {"ShadowBolt",ShadowBolt},
    {"Mutilation",Mutilation},
    {"LethalPoison",LethalPoison},
    {"Chloroform",Chloroform},
    {"Backstab",Backstab}
};

Interaction::Interaction(std::string name)
{
    className=name;
    Json::Value config=(*ConfigurationProvider::getConfig("config/interactions.json"))[name];
    manaCost=config.get("manaCost",0).asInt();
    std::string anim=config.get("anim","").asString();
    if(anim.compare("")!=0) {
        setAnimation(anim);
    }
    action=actions[name];
}

void Interaction::onAction(Creature *first, Creature *second)
{
    qDebug() << first->className.c_str() << "used"
             << this->className.c_str() << "against"
             << second->className.c_str();
    if(action) {
        action(first,second);
    }
}

int Interaction::getManaCost() {
    return manaCost;
}

Interaction *Interaction::getInteraction(std::string name)
{
    if(name.compare("")==0) {
        return 0;
    }
    return new Interaction(name);
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

void Attack(Creature *first, Creature *second)
{
    int dmg=first->getDmg();
    if(dmg)
    {
        second->hurt(dmg);
        Weapon *weapon=first->getWeapon();
        if(weapon)
        {
            Interaction *interaction=weapon->getInteraction();
            if(interaction)
            {
                interaction->onAction(first,second);
            }
        }
    }
}

void ElemStaff(Creature *first, Creature *second)
{
    Damage damage;
    damage.setFire(1);
    damage.setFrost(1);
    damage.setThunder(1);
    second->hurt(damage);
}

void DoubleAttack(Creature *first, Creature *second)
{
    Attack(first,second);
    Attack(first,second);
}

void SneakAttack(Creature *first, Creature *second)
{
    Attack(first,second);
    if(rand()%100>(100-second->getHpRatio()))
    {
        if(second->isAlive()) {
            Attack(first,second);
        }
    }
}

void Strike(Creature *first, Creature *second)
{
    if(first->getWeapon())
    {
        int dmg=first->getDmg();
        if(dmg)
        {
            second->hurt(dmg+first->getStats()->getDamage());
        }
    }
}

void Stunner(Creature *first, Creature *second)
{
    second->addEffect(new Effect("Stun",first,rand()%1+3));
}

void AbyssalShadows(Creature *first, Creature *second)
{
    second->addEffect(new Effect("AbyssalShadowsEffect",first,4));
}

void ArmorOfEndlessWinter(Creature *first, Creature *second)
{
    first->addEffect(new Effect("ArmorOfEndlessWinterEffect",first,3));
}

void ChaosBlast(Creature *first, Creature *second)
{
    Damage damage;
    damage.setFire(first->getMana()/2);
    damage.setThunder(first->getMana()/2);
    second->hurt(damage);
}

void Devour(Creature *first, Creature *second)
{
    int crit=first->getStats()->getCrit();
    first->getStats()->setCrit(0);
    int dmg=first->getDmg();
    if(dmg)
    {
        second->hurt(dmg);
        first->heal(dmg*0.75);
    }
    first->getStats()->setCrit(crit);
}

void EndlessPain(Creature *first, Creature *second)
{
    second->addEffect(new Effect("EndlessPainEffect",first,2));
}

void FrostBolt(Creature *first, Creature *second)
{
    Attack(first,second);
    Damage damage;
    damage.setFrost(first->getStats()->getIntelligence()*75.0/100.0);
    second->hurt(damage);
    //change to ice
}

void MagicMissile(Creature *first, Creature *second)
{
    int dmg=0;
    for(int i=0; i<first->getMana()/10+1; i++)
    {
        dmg+=rand()%4+1;
    }
    second->hurt(dmg);
}

void ShadowBolt(Creature *first, Creature *second)
{
    Damage damage;
    damage.setShadow(first->getDmg()*2.25);
    second->hurt(damage);
    if(rand()%2==0)
    {
        damage.setShadow(first->getWeapon()->getStats()->getDamage());
        second->addEffect(new Effect("AbyssalShadowsEffect",first,4));
    }
}

void Mutilation(Creature *first, Creature *second)
{
    second->addEffect(new Effect("MutilationEffect",first,4));
}

void LethalPoison(Creature *first, Creature *second)
{
    second->addEffect(new Effect("LethalPoisonEffect",first,6));
}

void Chloroform(Creature *first, Creature *second)
{
    second->addEffect(new Effect("ChloroformEffect",first,3));
}

void Backstab(Creature *first, Creature *second)
{
    second->hurt(first->getDmg()*2);
}
