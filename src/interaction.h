#ifndef INTERACTION_H
#define INTERACTION_H
#include <string>
#include <functional>
#include <unordered_map>
#include <src/map.h>
class Creature;
class QGraphicsSceneMouseEvent;
class Stats;
class Effect;

class Interaction : public MapObject {
	Q_OBJECT
public:
	Interaction();
	Interaction ( const Interaction &interaction );
	void onAction ( Creature *first, Creature *second );
	int getManaCost();
	virtual void onEnter();
	virtual void onMove();
	virtual void loadFromJson ( std::string name );
	virtual bool compare ( MapObject *item );
	virtual void performAction ( Creature*first,Creature*second );
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
	Effect ( std::string type, Creature *caster ,Creature * victim );
	int getTimeLeft();
	int getTimeTotal();
	Creature *getCaster();
	Creature *getVictim();
	bool apply ( Creature *creature );
	std::string className;
	Stats *getBonus();
	void setBonus ( Stats *value );
	Json::Value saveToJson();

private:
	static std::unordered_map<
	std::string, std::function<bool ( Effect *effect, Creature * ) > > effects;
	int timeLeft;
	int timeTotal;
	Stats *bonus;
	Creature *caster;
	Creature *victim;
};
bool StunEffect ( Effect *effect, Creature *creature );
bool EndlessPainEffect ( Effect *effect, Creature *creature );
bool AbyssalShadowsEffect ( Effect *effect, Creature *creature );
bool ArmorOfEndlessWinterEffect ( Effect *effect, Creature *creature );
bool MutilationEffect ( Effect *effect, Creature *creature );
bool LethalPoisonEffect ( Effect *effect, Creature *creature );
bool ChloroformEffect ( Effect *effect, Creature *creature );
bool BloodlashEffect ( Effect *effect, Creature *creature );
bool BarrierEffect ( Effect *effect, Creature *creature );

#endif // INTERACTION_H
