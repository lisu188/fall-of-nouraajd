#pragma once
#include <string>
#include <functional>
#include <map>
#include"CMap.h"
class CCreature;
class QGraphicsSceneMouseEvent;
class Stats;
class CEffect;

class CInteraction : public CGameObject,public CAnimatedObject {
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


class CEffect :public CGameObject {
	Q_OBJECT
	Q_PROPERTY ( int duration READ getDuration WRITE setDuration )
	Q_PROPERTY ( bool buff READ isBuff WRITE setBuff )
public:
	CEffect();
	CEffect ( const CEffect& );
	virtual ~CEffect();
	int getTimeLeft();
	int getTimeTotal();
	bool apply ( CCreature *creature );
	Stats *getBonus();
	void setBonus ( Stats *value );
	int getDuration();
	void setDuration ( int duration );
	virtual bool onEffect();
	bool isBuff() const;
	void setBuff ( bool value );
	CCreature *getCaster() ;
	void setCaster ( CCreature *value );
	CCreature *getVictim() ;
	void setVictim ( CCreature *value );
private:
	int timeLeft=0;
	int timeTotal=0;
	Stats *bonus=0;
	CCreature *caster=0;
	CCreature *victim=0;
	int duration=0;
	bool buff=false;
};

