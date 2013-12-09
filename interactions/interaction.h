#include <creatures/creature.h>

#ifndef INTERACTION_H
#define INTERACTION_H

class Interaction : private ListItem
{
public:
    Interaction();
    virtual ~Interaction();
    virtual void action(Creature *first,Creature *second);
    int getManaCost();
protected:
    void setAnimation(std::string path);
    virtual void mousePressEvent(QGraphicsSceneMouseEvent *event);
    int manaCost;
public:
    std::string className;

public:
    static Interaction *getAction(std::string name);

};

#endif // INTERACTION_H
