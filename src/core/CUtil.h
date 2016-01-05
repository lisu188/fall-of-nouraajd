#pragma once

#include "core/CGlobal.h"


class CGameObject;

struct Coords {
    Coords();

    Coords(int x, int y, int z);

    int x, y, z;

    bool operator==(const Coords &other) const;

    bool operator!=(const Coords &other) const;

    bool operator<(const Coords &other) const;

    bool operator>(const Coords &other) const;

    Coords operator-(const Coords &other) const;

    Coords operator+(const Coords &other) const;

    Coords operator*() const;

    double getDist(Coords a) const;
};

class CObjectData : public QMimeData {

public:
    CObjectData(std::shared_ptr<CGameObject> object);

    std::shared_ptr<CGameObject> getSource() const;

private:
    std::shared_ptr<CGameObject> source;
};

class CInvocationEvent : public QEvent {
public:
    static const QEvent::Type TYPE = static_cast<QEvent::Type> ( 1001 );

    CInvocationEvent(std::function<void()> target);

    std::function<void()> getTarget() const;

private:
    std::function<void()> const target;
};

class CInvocationHandler : public QObject {

public:
    static CInvocationHandler *instance();

    bool event(QEvent *event);

private:
    CInvocationHandler();
};

namespace std {
    template<>
    struct hash<Coords> {
        force_inline std::size_t  operator()(const Coords &coords) const {
            return vstd::hash_combine(coords.x, coords.y, coords.z);
        }
    };

    template<>
    struct hash<std::pair<int, int>> {
        force_inline std::size_t operator()(const std::pair<int, int> &pair) const {
            return vstd::hash_combine(pair.first, pair.second);
        }
    };
}

namespace vstd {
    template<typename T=std::string>
    T replace(T str, T from, T to) {
        size_t start_pos = str.find(from);
        if (start_pos == std::string::npos) {
            return false;
        }
        str.replace(start_pos, from.length(), to);
        return str;
    }

    template<typename T=std::string>
    T ltrim(T s) {
        s.erase(s.begin(), std::find_if(s.begin(), s.end(), std::not1(std::ptr_fun<int, int>(std::isspace))));
        return s;
    }

    template<typename T=std::string>
    T rtrim(T s) {
        s.erase(std::find_if(s.rbegin(), s.rend(), std::not1(std::ptr_fun<int, int>(std::isspace))).base(), s.end());
        return s;
    }

    template<typename T=std::string>
    T trim(T s) {
        return ltrim(rtrim(s));
    }

    template<typename T>
    std::string str(T c) {
        return std::string(c);
    }
}