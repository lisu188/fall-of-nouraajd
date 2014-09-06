#pragma once
#include "CAnimatedObject.h"
#include "lib/tmx/Tmx.h"
#include "Util.h"

class CMap;
class CMapObject : public CAnimatedObject {
	friend class CObjectHandler;
	Q_OBJECT
public:
	CMapObject();
	QString typeName;
	int posx, posy, posz;
	virtual void moveTo ( int x, int y, int z, bool silent = false );
	int getPosX() const;
	int getPosY() const;
	int getPosZ() const;
	void removeFromGame();
	virtual void onEnter();
	virtual void onMove();
	virtual void onCreate();
	virtual void onDestroy();
	Q_SLOT void move ( int x, int y );
	virtual void loadFromJson ( QString name ) = 0;
	void loadFromProps ( Tmx::PropertySet set );
	virtual void setMap ( CMap *map );
	CMap *getMap();
	void setVisible ( bool vis );
	Coords getCoords();
	void setCoords ( Coords coords );
	PROPERTY_ACCESSOR
protected:
	CMap *map = 0;
	QGraphicsSimpleTextItem statsView;

public:
	void setNumber ( int i, int x );
	virtual bool compare ( CMapObject *item );

protected:
	QString tooltip;
	virtual void hoverEnterEvent ( QGraphicsSceneHoverEvent *event );
	virtual void hoverLeaveEvent ( QGraphicsSceneHoverEvent *event );
};

class CEvent : public CMapObject {
	Q_OBJECT
	Q_PROPERTY ( QString script READ getScript WRITE setScript USER true )
	Q_PROPERTY ( bool enabled READ isEnabled WRITE setEnabled USER true )
public:
	CEvent();
	CEvent ( const CEvent & );
	void onEnter();
	void onMove();
	void loadFromJson ( QString );
	// PROPERTIES
	QString getScript() const;
	void setScript ( const QString &value );
	bool isEnabled();
	void setEnabled ( bool enabled );

private:
	bool enabled = true;
	QString script;
};
