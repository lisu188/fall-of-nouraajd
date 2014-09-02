#ifndef INTERACTION_H
#define INTERACTION_H
#include <string>
#include <functional>
#include <unordered_map>
#include"CMap.h"
class CCreature;
class QGraphicsSceneMouseEvent;
class Stats;
class Effect;

class CInteraction : public CMapObject {
	Q_OBJECT
public:
	CInteraction();
	CInteraction ( const CInteraction &interaction );
	void onAction ( CCreature *first, CCreature *second );
	int getManaCost();
	virtual void onEnter();
	virtual void onMove();
	virtual void loadFromJson ( std::string name );
	virtual bool compare ( CMapObject *item );
	virtual void performAction ( CCreature*first,CCreature*second );
	virtual bool configureEffect ( Effect*effect );

protected:
	void mousePressEvent ( QGraphicsSceneMouseEvent *event );
	int manaCost;
	std::string effect;

private:
	QGraphicsSimpleTextItem statsView;
};


class Effect {
public:
	Effect ( std::string type, CCreature *caster ,CCreature * victim );
	int getTimeLeft();
	int getTimeTotal();
	CCreature *getCaster();
	CCreature *getVictim();
	bool apply ( CCreature *creature );
	std::string className;
	Stats *getBonus();
	void setBonus ( Stats *value );
	Json::Value saveToJson();

private:
	static std::unordered_map<
	std::string, std::function<bool ( Effect *effect, CCreature * ) > > effects;
	int timeLeft;
	int timeTotal;
	Stats *bonus;
	CCreature *caster;
	CCreature *victim;
};
bool StunEffect ( Effect *effect, CCreature *creature );
bool EndlessPainEffect ( Effect *effect, CCreature *creature );
bool AbyssalShadowsEffect ( Effect *effect, CCreature *creature );
bool ArmorOfEndlessWinterEffect ( Effect *effect, CCreature *creature );
bool MutilationEffect ( Effect *effect, CCreature *creature );
bool LethalPoisonEffect ( Effect *effect, CCreature *creature );
bool ChloroformEffect ( Effect *effect, CCreature *creature );
bool BloodlashEffect ( Effect *effect, CCreature *creature );
bool BarrierEffect ( Effect *effect, CCreature *creature );

#endif // INTERACTION_H
