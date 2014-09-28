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
	Q_PROPERTY ( int duration READ getDuration WRITE setDuration )
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
	int getDuration();
	void setDuration ( int duration );
	virtual void onEffect();
private:
	static std::map<
	QString, std::function<bool ( CEffect *effect ) > > effects;
	int timeLeft=0;
	int timeTotal=0;
	Stats *bonus=0;
	CCreature *caster=0;
	CCreature *victim=0;
	int duration=0;
};

bool StunEffect ( CEffect * );
bool EndlessPainEffect ( CEffect *effect );
bool AbyssalShadowsEffect ( CEffect *effect );
bool ArmorOfEndlessWinterEffect ( CEffect * );
bool MutilationEffect ( CEffect *effect );
bool LethalPoisonEffect ( CEffect *effect );
bool ChloroformEffect ( CEffect * );
bool BloodlashEffect ( CEffect *effect );
bool BarrierEffect ( CEffect * );

#endif // INTERACTION_H
