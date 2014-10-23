#pragma once
#include <QGraphicsPixmapItem>
#include <QJsonObject>
#include <map>
#include <string>
#include <functional>
#include "CMapObject.h"

class CGameScene;
class CCreature;
class CTile : public CAnimatedObject,public Constructible {
	Q_OBJECT
	Q_PROPERTY ( bool canStep READ canStep WRITE setCanStep USER true )
	Q_PROPERTY ( QString objectType READ getObjectType WRITE setObjectType USER true )
public:
	CTile();
	CTile ( const CTile &tile );
	virtual void onStep ( CCreature * );
	void move ( int x, int y, int z ) ;
	void moveTo ( int x,int y,int z );
	Coords getCoords();
	bool canStep() const;
	void setCanStep ( bool canStep );
	void addToScene ( CGameScene *scene );
	void removeFromScene ( CGameScene *scene );

	virtual void setObjectName ( const QString &name ) override;
	virtual void setObjectType ( const QString &type );

	virtual QString getObjectName() const override;
	virtual QString getObjectType() const override;

	virtual CMap *getMap() override;
	virtual void setMap ( CMap *value ) override;

	virtual ~CTile();

private:
	CMap * map=0;
	bool step=false;
	int posx=0,posy=0,posz=0;
	QString objectType;
	void setXYZ ( int x, int y, int z );
};
