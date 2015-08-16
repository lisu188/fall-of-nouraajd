#include "CUtil.h"
#include "templates/hash.h"
#include "object/CGameObject.h"

Coords::Coords() { x = y = z = 0; }

Coords::Coords ( int x, int y, int z ) : x ( x ), y ( y ), z ( z ) {}

bool Coords::operator== ( const Coords &other ) const {
    return ( x == other.x && y == other.y && z == other.z );
}

bool Coords::operator!= ( const Coords &other ) const {
    return !operator== ( other );
}

bool Coords::operator< ( const Coords &other ) const {
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

bool Coords::operator> ( const Coords &other ) const {
    return !operator< ( other );
}

Coords Coords::operator- ( const Coords &other ) const {
    return Coords ( x-other.x,y-other.y,z-other.z );
}

Coords Coords::operator+ ( const Coords &other ) const {
    return Coords ( x+other.x,y+other.y,z+other.z );
}

Coords Coords::operator*() const {
    return *this;
}

double Coords::getDist ( Coords a ) const {
    double x = this->x - a.x;
    x *= x;
    double y = this->y - a.y;
    y *= y;
    return sqrt ( x + y );
}

CObjectData::CObjectData ( std::shared_ptr<CGameObject> object ) :source ( object ) {

}

std::shared_ptr<CGameObject> CObjectData::getSource() const {
    return source;
}


