#pragma once

#include "core/CGlobal.h"
#include "vstd/vstd.h"
#include "vstd/vstd.h"

class CGameObject;

struct Coords {
    Coords();

    Coords ( int x, int y, int z );

    int x, y, z;

    bool operator== ( const Coords &other ) const;

    bool operator!= ( const Coords &other ) const;

    bool operator< ( const Coords &other ) const;

    bool operator> ( const Coords &other ) const;

    Coords operator- ( const Coords &other ) const;

    Coords operator+ ( const Coords &other ) const;

    Coords operator*() const;

    double getDist ( Coords a ) const;
};

class CObjectData : public QMimeData {
    Q_OBJECT
public:
    CObjectData ( std::shared_ptr<CGameObject> object );

    std::shared_ptr<CGameObject> getSource() const;

private:
    std::shared_ptr<CGameObject> source;
};

class CInvocationEvent : public QEvent {
public:
    static const QEvent::Type TYPE = static_cast<QEvent::Type> ( 1001 );

    CInvocationEvent ( std::function<void() > target );

    std::function<void() > getTarget() const;

private:
    std::function<void() > const target;
};

class CInvocationHandler : public QObject {
    Q_OBJECT
public:
    static CInvocationHandler *instance();

    bool event ( QEvent *event );

private:
    CInvocationHandler();
};

namespace std {
    template<>
    struct hash<Coords> {
        force_inline std::size_t  operator() ( const Coords &coords ) const {
            return vstd::hash_combine ( coords.x, coords.y, coords.z );
        }
    };

    template<>
    struct hash<QString> {
        force_inline std::size_t operator() ( const QString &string ) const {
            return vstd::hash_combine ( string.toStdString() );
        }
    };

    template<>
    struct hash<std::pair<int, int>> {
        force_inline std::size_t operator() ( const std::pair<int, int> &pair ) const {
            return vstd::hash_combine ( pair.first, pair.second );
        }
    };
}