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
	T createMapObject ( QString type ) {
		return dynamic_cast<T> ( _createMapObject ( type ) );
	}
	void logProperties ( CMapObject *object );
	QJsonObject *getObjectConfig() ;
	void setObjectConfig ( const QJsonObject &value );
private:
	CMapObject *_createMapObject ( QString type );
	void setProperty ( QObject * object , QString key, QJsonValue value );
	QMetaProperty getProperty ( QObject * object ,QString name );
	CMap *map;
	QJsonObject objectConfig;
};
