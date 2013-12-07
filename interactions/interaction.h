#include <creatures/creature.h>

#ifndef INTERACTION_H
#define INTERACTION_H

class Interaction : private ListItem
{
public:
    Interaction();
    virtual ~Interaction();
    virtual void action(Creature *first,Creature *second);
    int getManaCost() {
        return manaCost;
    }
protected:
    void setAnimation(std::string path);
    virtual void mousePressEvent(QGraphicsSceneMouseEvent *event);
    int manaCost;
public:
    std::string className;
};

#endif // INTERACTION_H
