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
    virtual Interaction *clone()=0;
protected:
    void setAnimation(std::string path);
    virtual void mousePressEvent(QGraphicsSceneMouseEvent *event);
    int manaCost;
public:
    std::string className;

public:
    static Interaction *getAction(std::string name);
    static void terminate();
private:
    static std::list<Interaction*> actions;
    static void init();
};

#endif // INTERACTION_H
