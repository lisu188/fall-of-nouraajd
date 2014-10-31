#pragma once
#include <QObject>
#include <QJsonObject>
#include <QList>
#include <QFile>

#include "CMapObject.h"


class CGameObject;
class ATypeHandler;
class CMap;

class CGameEvent:public QObject {
	Q_OBJECT
	Q_ENUMS ( Type )
public:
	enum Type {
		onEnter,onTurn,onCreate,onDestroy,onLeave,onUse,onEquip,onUnequip,onStep
	};
	CGameEvent ( Type type,CGameObject *cause=0 );
	Type getType() const;
	CGameObject *getCause() const;

private:
	const Type type;
	CGameObject *cause=0;
};

class CEventHandler : public QObject {
	Q_OBJECT
public:
	CEventHandler ( CMap *map );
	void gameEvent ( CGameEvent *event, CGameObject *mapObject ) const;
private:
	CMap*map=0;
};

class CObjectHandler : public QObject {
	Q_OBJECT
public:
	CObjectHandler ( CMap *map );
	template<typename T>
	T createMapObject ( QString type ) const {
		CGameObject *object= _createObject ( type ) ;
		T casted=dynamic_cast<T> ( object );
		if ( casted==nullptr ) {
			delete object;
		}
		return casted;
	}
    void registerHandler(ATypeHandler *handler);
	void logProperties ( CGameObject *object ) const;
	const QJsonObject *getObjectConfig() const;
    CMap *getMap();

    std::list<ATypeHandler*> handlers;
private:
    ATypeHandler *getHandler ( QString name )const;
	CGameObject *_createObject ( QString type ) const;
	void setProperty ( CGameObject * object , QString key, QJsonValue value ) const;
	QMetaProperty getProperty ( CGameObject * object ,QString name ) const;
	CMap *map=0;
	QJsonObject objectConfig;
};

enum CResType {
	CONFIG,MAP,SCRIPT,IMAGE
};

class CResourcesHandler : public QObject {
	Q_OBJECT
public:
	static CResourcesHandler *getInstance();
	QFile *getResource ( QString path );
	QString getResourceAsString ( QString path );
	QString getPath ( QString path );
	QSet<QString> getFiles ( CResType type );

private:
	static QList<QString> searchPath;
	CResourcesHandler();
};

class CGameObject;
class ATypeHandler : public QObject {
	Q_OBJECT
public:
	virtual CGameObject *create ( QString ) =0;
	virtual QString getHandlerName() =0;
protected:
    CObjectHandler *getObjectHandler();
};

class CTypeHandler : public ATypeHandler {
	Q_OBJECT
public:
	virtual CGameObject *create ( QString name ) override;
	virtual QString getHandlerName() override;
};

class PyTypeHandler : public ATypeHandler {
	Q_OBJECT
public:
	virtual CGameObject *create ( QString name ) override;
	virtual QString getHandlerName() override;
};

class AGamePanel;
class CGuiHandler:public QObject {
	Q_OBJECT
public:
	CGuiHandler ( CMap*map );
	void showMessage ( QString msg );
	AGamePanel *getPanel ( QString panel );
	bool isAnyPanelVisible();
	void refresh();
private:
	std::map<QString,AGamePanel*> panels;
	void initPanels();
	CMap*map;
};



