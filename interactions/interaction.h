#ifndef INTERACTION_H
#define INTERACTION_H

#include <string>
#include <functional>
#include <unordered_map>
#include <view/listitem.h>

class Creature;
class QGraphicsSceneMouseEvent;

class Interaction : private ListItem
{
public:
    std::string className;
    void onAction(Creature *first,Creature *second);
    int getManaCost();
    static Interaction *getInteraction(std::string name);
protected:
    void setAnimation(std::string path);
    void mousePressEvent(QGraphicsSceneMouseEvent *event);
    int manaCost;
private:
    std::function<void (Creature *, Creature *)> action;
    Interaction(std::string name);
    static std::unordered_map<std::string,std::function<void (Creature *, Creature *)>> actions;

};

void Attack(Creature *first,Creature *second);
void ElemStaff(Creature *first,Creature *second);
void DoubleAttack(Creature *first, Creature *second);
void SneakAttack(Creature *first, Creature *second);
void Strike(Creature *first, Creature *second);
void Stunner(Creature *first, Creature *second);
void AbyssalShadows(Creature *first, Creature *second);
void ArmorOfEndlessWinter(Creature *first, Creature *second);
void ChaosBlast(Creature *first, Creature *second);
void Devour(Creature *first, Creature *second);
void EndlessPain(Creature *first, Creature *second);
void FrostBolt(Creature *first, Creature *second);
void MagicMissile(Creature *first, Creature *second);
void ShadowBolt(Creature *first, Creature *second);

#endif // INTERACTION_H
