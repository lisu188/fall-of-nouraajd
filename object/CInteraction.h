#pragma once
#include <string>
#include <functional>
#include <map>
#include"CMap.h"
class CCreature;
class QGraphicsSceneMouseEvent;
class Stats;
class CEffect;

class CInteraction : public CGameObject {
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

	int manaCost;
	QString effect;

private:
	QGraphicsSimpleTextItem statsView;
};


