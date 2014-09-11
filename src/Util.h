#pragma once
#include <QMimeData>

#define PY_PROPERTY_ACCESSOR(CLASS)\
.def ( "getStringProperty",&CLASS::getStringProperty )\
.def ( "getNumericProperty",&CLASS::getNumericProperty )\
.def ( "getBoolProperty",&CLASS::getBoolProperty )\
.def ( "setStringProperty",&CLASS::setStringProperty )\
.def ( "setNumericProperty",&CLASS::setNumericProperty )\
.def ( "setBoolProperty",&CLASS::setBoolProperty )\
.def ( "incProperty",&CLASS::incProperty )\
 
struct Coords {
	Coords() { x = y = z = 0; }
	Coords ( int x, int y, int z ) : x ( x ), y ( y ), z ( z ) {}
	int x, y, z;
	bool operator== ( const Coords &other ) const {
		return ( x == other.x && y == other.y && z == other.z );
	}
	bool operator< ( const Coords &other ) const {
		if ( x < other.x ) {
			return true;
		}
		if ( y < other.y && x == other.x ) {
			return true;
		}
		if ( z < other.z && x == other.x && y == other.y ) {
			return true;
		}
		return false;
	}
	int getDist ( Coords a ) {
		double x = this->x - a.x;
		x *= x;
		double y = this->y - a.y;
		y *= y;
		return sqrt ( x + y );
	}
};

struct CoordsHasher {
	std::size_t operator() ( const Coords &coords ) const {
		using std::size_t;
		int a = ( size_t ) coords.x;
		int b = ( size_t ) coords.y;
		int c = ( size_t ) coords.z;
		return ( size_t ) ( a ^ b ) ^ ( b ^ c ) ^ ( a ^ c );
	}

};

template <class T>
class Comparer {
public:
	bool operator() ( T *first, T *second ) {
		if ( !first ) {
			return false;
		}
		if ( !second ) {
			return true;
		}
		return first->compare ( second );
	}
};

class QObject;
class CObjectData:public QMimeData {
	Q_OBJECT
public:
	QObject *source;
	CObjectData ( QObject *source ) {
		this->source=source;
	}
	QObject *getSource() const {
		return source;
	}
};
