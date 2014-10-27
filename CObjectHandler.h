#pragma once
#include <QObject>
#include <QJsonObject>
#include "CTypeHandler.h"
#include "CMapObject.h"
class CMap;
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
	void logProperties ( CGameObject *object ) const;
	const QJsonObject *getObjectConfig() const;
private:
	CGameObject *_createObject ( QString type ) const;
	void setProperty ( CGameObject * object , QString key, QJsonValue value ) const;
	QMetaProperty getProperty ( CGameObject * object ,QString name ) const;
	CMap *map=0;
	QJsonObject objectConfig;
};
