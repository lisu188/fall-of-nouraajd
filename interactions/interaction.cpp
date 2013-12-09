#include "interaction.h"

#include <creatures/players/player.h>

#include <view/gamescene.h>
#include <view/gameview.h>

#include <view/playerstatsview.h>
#include <view/fightview.h>

#include <items/armors/armor.h>
#include <QDebug>

Interaction::Interaction() {
    className = "Interaction";
    manaCost = 0;
}

int Interaction::getManaCost() { return manaCost; }

Interaction::~Interaction() {}

void Interaction::action(Creature *first, Creature *second) {
    qDebug() << first->className.c_str() << " used " << this->className.c_str() << " against "
             << second->className.c_str();
}

void Interaction::setAnimation(std::string path) { ListItem::setAnimation(path); }

void Interaction::mousePressEvent(QGraphicsSceneMouseEvent *event) {
    Player *player = GameScene::getPlayer();
    if (player->getFightList()->size() == 0)
        return;
    if (manaCost > player->getMana())
        return;
    Creature *creature = FightView::selected;
    if (!creature)
        return;
    action(player, creature);
    player->takeMana(manaCost);

    Armor *armor = creature->getArmor();
    if (armor) {
        Interaction *interaction = armor->getInteraction();
        if (interaction)
            interaction->action(creature, player);
    }

    if (!creature->isAlive()) {
        qDebug() << player->className.c_str() << "defeated" << creature->className.c_str() << "\n";
        player->addExpScaled(creature->getScale());
        player->addItem(creature->getLoot());
        creature->removeFromGame();
        player->getFightList()->remove(creature);
        if (player->getFightList()->size() == 0) {
            GameScene::getView()->getFightView()->setVisible(false);
            FightView::selected = 0;
        } else {
            FightView::selected = player->getFightList()->front();
        }
        player->getStatsView()->update();
    } else {
        qDebug() << "";
        for (std::list<Creature *>::iterator it = player->getFightList()->begin(); it != player->getFightList()->end();
             it++) {
            (*it)->fight(player);
        }
    }
    GameScene::getView()->getFightView()->update();
    if (!player->isAlive()) {
        GameScene::getView()->close();
    }
}

#include <interactions/spells/abyssalshadows.h>
#include <interactions/attacks/attack.h>
#include <interactions/attacks/elemstaff.h>
#include <interactions/skills/doubleattack.h>
#include <interactions/skills/sneakattack.h>
#include <interactions/skills/strike.h>
#include <interactions/skills/stunner.h>
#include <interactions/spells/chaosblast.h>
#include <interactions/spells/frostbolt.h>
#include <interactions/spells/magicmissile.h>

Interaction *Interaction::getAction(std::string name) {
    if (name == "AbyssalShadows")
        return new AbyssalShadows();
    if (name == "Attack")
        return new Attack();
    if (name == "ElemStaff")
        return new ElemStaff();
    if (name == "DoubleAttack")
        return new DoubleAttack();
    if (name == "SneakAttack")
        return new SneakAttack();
    if (name == "Strike")
        return new Strike();
    if (name == "Stunner")
        return new Stunner();
    if (name == "ChaosBlast")
        return new ChaosBlast();
    if (name == "FrostBolt")
        return new FrostBolt();
    if (name == "MagicMissile")
        return new MagicMissile();
    return nullptr;
}
