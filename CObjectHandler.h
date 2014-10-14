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
		CMapObject *object= _createMapObject ( type ) ;
		T casted=dynamic_cast<T> ( object );
		if ( casted==nullptr ) {
			delete object;
		}
		return casted;
	}
	void logProperties ( CMapObject *object ) const;
	const QJsonObject *getObjectConfig() const;
private:
	CMapObject *_createMapObject ( QString type ) const;
	void setProperty ( QObject * object , QString key, QJsonValue value ) const;
	QMetaProperty getProperty ( QObject * object ,QString name ) const;
	CMap *map=0;
	QJsonObject objectConfig;
};
