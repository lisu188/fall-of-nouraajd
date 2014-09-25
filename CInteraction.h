#ifndef INTERACTION_H
#define INTERACTION_H
#include <string>
#include <functional>
#include <map>
#include"CMap.h"
class CCreature;
class QGraphicsSceneMouseEvent;
class Stats;
class CEffect;

class CInteraction : public CMapObject {
	Q_OBJECT
	Q_PROPERTY ( int manaCost READ getManaCost  WRITE setManaCost USER true )
	Q_PROPERTY ( QString effect READ getEffect WRITE setEffect USER true )
public:
	CInteraction();
	CInteraction ( const CInteraction & );
	void onAction ( CCreature *first, CCreature *second );
	virtual void performAction ( CCreature*, CCreature* );
	virtual bool configureEffect ( CEffect* );

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


class CEffect :public CMapObject {
	Q_OBJECT
public:
	CEffect ( QString type, CCreature *caster ,CCreature * victim );
	CEffect();
	CEffect ( const CEffect& );
	int getTimeLeft();
	int getTimeTotal();
	CCreature *getCaster();
	CCreature *getVictim();
	bool apply ( CCreature *creature );
	QString className;
	Stats *getBonus();
	void setBonus ( Stats *value );

private:
	static std::map<
	QString, std::function<bool ( CEffect *effect, CCreature * ) > > effects;
	int timeLeft;
	int timeTotal;
	Stats *bonus=0;
	CCreature *caster;
	CCreature *victim;
};

bool StunEffect ( CEffect *, CCreature * );
bool EndlessPainEffect ( CEffect *effect, CCreature *creature );
bool AbyssalShadowsEffect ( CEffect *effect, CCreature *creature );
bool ArmorOfEndlessWinterEffect ( CEffect *, CCreature *creature );
bool MutilationEffect ( CEffect *effect, CCreature *creature );
bool LethalPoisonEffect ( CEffect *effect, CCreature *creature );
bool ChloroformEffect ( CEffect *, CCreature *creature );
bool BloodlashEffect ( CEffect *effect, CCreature *creature );
bool BarrierEffect ( CEffect *, CCreature * );

#endif // INTERACTION_H
