#include "CReflection.h"
#include <QObject>

CReflection *CReflection::getInstance() {
	static CReflection instance;
	return &instance;
}

bool CReflection::checkInheritance ( std::string base, std::string inherited ) {
	if ( base.compare ( inherited ) ==0 ) {
		return false;
	}
	int classId = QMetaType::type ( inherited.append ( "*" ).c_str() );
	const QMetaObject *metaObject = QMetaType::metaObjectForType ( classId );
	while ( metaObject ) {
		std::string className = metaObject->className();
		if ( className.compare ( base ) == 0 ) {
			break;
		}
		metaObject = metaObject->superClass();
	}
	return metaObject != 0 ;
}
