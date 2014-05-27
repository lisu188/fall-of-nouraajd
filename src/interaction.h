#ifndef INTERACTION_H
#define INTERACTION_H

#include <string>
#include <functional>
#include <unordered_map>
#include <src/listitem.h>

class Creature;
class QGraphicsSceneMouseEvent;
class Stats;

class Interaction : public ListItem
{
    Q_OBJECT
public:
    Interaction();
    Interaction(const Interaction& interaction);
    void onAction(Creature *first, Creature *second);
    int getManaCost();
    static Interaction *getInteraction(std::string name);
    virtual void onEnter();
    virtual void onMove();
    virtual void loadFromJson(std::string name);
    virtual bool compare(ListItem *item);
protected:
    void mousePressEvent(QGraphicsSceneMouseEvent *event);
    int manaCost;
private:
    static std::unordered_map<std::string, std::function<void (Creature *, Creature *)>> actions;
    std::string effect;
    QGraphicsSimpleTextItem statsView;
};
Q_DECLARE_METATYPE(Interaction)

void Attack(Creature *first, Creature *second);
void ElemStaff(Creature *first, Creature *second);
void DoubleAttack(Creature *first, Creature *second);
void SneakAttack(Creature *first, Creature *second);
void Strike(Creature *first, Creature *second);
void ArmorOfEndlessWinter(Creature *first, Creature *second);
void ChaosBlast(Creature *first, Creature *second);
void Devour(Creature *first, Creature *second);
void FrostBolt(Creature *first, Creature *second);
void MagicMissile(Creature *first, Creature *second);
void ShadowBolt(Creature *first, Creature *second);
void Mutilation(Creature *first, Creature *second);
void LethalPoison(Creature *first, Creature *second);
void Backstab(Creature *first, Creature *second);
void Bloodlash(Creature *first, Creature *second);
void DeathStrike(Creature *first, Creature *second);
void Barrier(Creature *first, Creature *second);
void BloodThirst(Creature *first, Creature *second);

class Effect
{
public:
    Effect(std::string type, Creature *caster);
    int getTimeLeft();
    int getTimeTotal();
    Creature *getCaster();
    bool apply(Creature *creature);
    std::string className;
    Stats *getBonus();
    void setBonus(Stats *value);
    Json::Value saveToJson();
private:
    static std::unordered_map<std::string, std::function<bool (Effect *effect, Creature *)>> effects;
    int timeLeft;
    int timeTotal;
    Stats *bonus;
    Creature *caster;

};
bool StunEffect(Effect *effect, Creature *creature);
bool EndlessPainEffect(Effect *effect, Creature *creature);
bool AbyssalShadowsEffect(Effect *effect, Creature *creature);
bool ArmorOfEndlessWinterEffect(Effect *effect, Creature *creature);
bool MutilationEffect(Effect *effect, Creature *creature);
bool LethalPoisonEffect(Effect *effect, Creature *creature);
bool ChloroformEffect(Effect *effect, Creature *creature);
bool BloodlashEffect(Effect *effect, Creature *creature);
bool BarrierEffect(Effect *effect, Creature *creature);


#endif // INTERACTION_H
