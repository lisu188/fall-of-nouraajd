#include "Util.h"
#include "object/CGameObject.h"
#include <QDebug>
#include <QThreadPool>

CObjectData::CObjectData ( CGameObject *source ) {
    setParent ( source );
    this->source=source;
}

CGameObject *CObjectData::getSource() const {
    return source;
}


std::size_t std::hash<QString>::operator() ( const QString &string ) const {
    return stringHash ( string.toStdString() );
}

std::size_t std::hash<Coords>::operator() ( const Coords &coords ) const {
    using std::size_t;
    size_t hash =coords.x*13;
    hash=hash*17+coords.y;
    hash=hash*31+coords.z;
    return hash;
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

int Coords::getDist ( Coords a ) {
    double x = this->x - a.x;
    x *= x;
    double y = this->y - a.y;
    y *= y;
    return sqrt ( x + y );
}


void AsyncTask::async ( std::function<void () > target ) {
    QThreadPool::globalInstance()->start ( new AsyncTask ( target ) );
}

void AsyncTask::run() {
    QMetaObject::invokeMethod ( this,"call",Qt::ConnectionType::BlockingQueuedConnection );
}

AsyncTask::AsyncTask ( std::function<void () > target ) :target ( target ) {

}

void  AsyncTask::call() {
    target();
}
