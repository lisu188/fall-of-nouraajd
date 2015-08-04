#include "CUtil.h"
#include "object/CGameObject.h"

CObjectData::CObjectData ( std::shared_ptr<CGameObject> object ) :source ( object ) {

}

std::shared_ptr<CGameObject> CObjectData::getSource() const {
    return source;
}

std::size_t std::hash<QString>::operator() ( const QString &string ) const {
    return stringHash ( string.toStdString() );
}

std::size_t std::hash<Coords>::operator() ( const Coords &coords ) const {
    return int_hash ( coords.x,coords.y,coords.z );
}

Coords::Coords() { x = y = z = 0; }

Coords::Coords ( int x, int y, int z ) : x ( x ), y ( y ), z ( z ) {}

bool Coords::operator== ( const Coords &other ) const {
    return ( x == other.x && y == other.y && z == other.z );
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

Coords Coords::operator- ( const Coords &other ) const {
    return Coords ( x-other.x,y-other.y,z-other.z );
}

Coords Coords::operator*() const {
    return Coords ( x,y,z );
}

double Coords::getDist ( Coords a ) {
    double x = this->x - a.x;
    x *= x;
    double y = this->y - a.y;
    y *= y;
    return sqrt ( x + y );
}


std::size_t std::hash<std::pair<int, int> >::operator() ( const std::pair<int, int> &pair ) const {
    return int_hash ( pair.first,pair.second );
}


inline std::size_t int_hash() {
    return 0;
}
