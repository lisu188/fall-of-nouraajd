#ifndef INTERACTION_H
#define INTERACTION_H
#include <string>
#include <functional>
#include <map>
#include"CMap.h"
class CCreature;
class QGraphicsSceneMouseEvent;
class Stats;
class Effect;

class CInteraction : public CMapObject {
	Q_OBJECT
	Q_PROPERTY ( int manaCost READ getManaCost  WRITE setManaCost USER true )
	Q_PROPERTY ( QString effect READ getEffect WRITE setEffect USER true )
public:
	CInteraction();
	CInteraction ( const CInteraction & );
	void onAction ( CCreature *first, CCreature *second );
	virtual void onEnter();
	virtual void onMove();
	virtual bool compare ( CMapObject *item );
	virtual void performAction ( CCreature*, CCreature* );
	virtual bool configureEffect ( Effect* );

	QString getEffect() const;
	void setEffect ( const QString &value );

	int getManaCost() const;
	void setManaCost ( int value );

protected:
	void mousePressEvent ( QGraphicsSceneMouseEvent * );
	int manaCost;
	QString effect;

private:
	QGraphicsSimpleTextItem statsView;
};


class Effect {
public:
	Effect ( QString type, CCreature *caster ,CCreature * victim );
	int getTimeLeft();
	int getTimeTotal();
	CCreature *getCaster();
	CCreature *getVictim();
	bool apply ( CCreature *creature );
	QString className;
	Stats *getBonus();
	void setBonus ( Stats *value );
	QJsonObject saveToJson();

private:
	static std::map<
	QString, std::function<bool ( Effect *effect, CCreature * ) > > effects;
	int timeLeft;
	int timeTotal;
	Stats *bonus;
	CCreature *caster;
	CCreature *victim;
};
bool StunEffect ( Effect *, CCreature * );
bool EndlessPainEffect ( Effect *effect, CCreature *creature );
bool AbyssalShadowsEffect ( Effect *effect, CCreature *creature );
bool ArmorOfEndlessWinterEffect ( Effect *, CCreature *creature );
bool MutilationEffect ( Effect *effect, CCreature *creature );
bool LethalPoisonEffect ( Effect *effect, CCreature *creature );
bool ChloroformEffect ( Effect *, CCreature *creature );
bool BloodlashEffect ( Effect *effect, CCreature *creature );
bool BarrierEffect ( Effect *, CCreature * );

#endif // INTERACTION_H
