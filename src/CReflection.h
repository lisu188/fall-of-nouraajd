#pragma once
#include <list>
#include <QObject>
#include <QDebug>
#include <mutex>
#include <set>
#define PP_CAT(a, b) PP_CAT_I(a, b)
#define PP_CAT_I(a, b) PP_CAT_II(~, a ## b)
#define PP_CAT_II(p, res) res

#define UNIQUE_NAME(base) PP_CAT(base, __LINE__)

#define REFLECT(CLASS) \
Q_DECLARE_METATYPE(CLASS) \
Q_DECLARE_METATYPE(CLASS*) \
CReflectionHelper<CLASS> UNIQUE_NAME(CReflectionHelper##CLASS##BASE) ; \
CReflectionHelper<CLASS*> UNIQUE_NAME(CReflectionHelper##CLASS##POINTER) ; \
 
class CReflection {
public:
	static CReflection * getInstance();
	bool checkInheritance ( std::string base, std::string inherited );
	template<typename T>
	void registerType() {
		static std::mutex mutex;
		std::unique_lock<std::mutex> lock ( mutex );
		metaTypes.insert ( qRegisterMetaType<T>() );
	}
	template<typename T>
	std::list<T> getInherited() {
		std::list<T> objects;
		const QMetaObject *mObject=QMetaType::metaObjectForType ( qRegisterMetaType<T>() );
		if ( mObject ) {
			std::string base=mObject->className();
			for ( auto it=metaTypes.begin(); it!=metaTypes.end(); it++ ) {
				mObject=QMetaType::metaObjectForType ( *it );
				if ( mObject && checkInheritance ( base,mObject->className() ) ) {
					std::string typeName=mObject->className();
					int typeId=QMetaType::type ( typeName.c_str() );
					T object= ( T ) QMetaType::create ( typeId );
					objects.push_back (  object );
				}
			}
		} else {
			qDebug() <<"No registered object";
		}
		return objects;
	}
	std::set<int> metaTypes;
private:
	CReflection() {}
};

template<class T>
class CReflectionHelper {
public:
	CReflectionHelper() {
		CReflection::getInstance()->registerType<T>();
	}
};
