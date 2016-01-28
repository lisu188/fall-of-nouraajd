#pragma once

#include "core/CGlobal.h"
#include "core/CUtil.h"


class CGameEvent;

class CMap;

class CGameObject : public vstd::stringable, public std::enable_shared_from_this<CGameObject> {
V_META(CGameObject, vstd::meta::empty,
       V_PROPERTY(CGameObject, std::string, name, getName, setName),
       V_PROPERTY(CGameObject, std::string, type, getType, setType)
)

public:
    CGameObject();

    virtual ~CGameObject();

    std::shared_ptr<CMap> getMap();

    void setMap(std::shared_ptr<CMap> map);

    template<typename T=CGameObject>
    std::shared_ptr<T> ptr() const {
        return vstd::cast<T>(const_cast<CGameObject *>(this)->shared_from_this());
    }

    template<typename T>
    void setProperty(std::string name, T property) {
        this->meta()->set_property<CGameObject, T>(name, this->ptr(), property);
    }

    template<typename T>
    T getProperty(std::string name) const {
        return this->meta()->get_property<CGameObject, T>(name, this->ptr());
    }

    void setStringProperty(std::string name, std::string value);

    void setBoolProperty(std::string name, bool value);

    void setNumericProperty(std::string name, int value);

    std::string getStringProperty(std::string name) const;

    bool getBoolProperty(std::string name) const;

    int getNumericProperty(std::string name) const;

    template<typename T=CGameObject>
    void setObjectProperty(std::string name, std::shared_ptr<T> object) {
        setProperty(name, boost::any(object));
    }

    template<typename T=CGameObject>
    std::shared_ptr<T> getObjectProperty(std::string name) {
        return getProperty<std::shared_ptr<T>>(name);
    }

    template<typename T=CGameObject>
    std::shared_ptr<T> clone() {
        return vstd::cast<T>(_clone());
    }

    void incProperty(std::string name, int value);

//    virtual std::string getTooltip() const;
//
//    virtual void setTooltip ( const std::string &value );

protected:
    //TODO: tooltip
//    virtual void hoverEnterEvent ( QGraphicsSceneHoverEvent *event ) override final;
//
//    virtual void hoverLeaveEvent ( QGraphicsSceneHoverEvent *event ) override final;
//
//    virtual void mousePressEvent ( QGraphicsSceneMouseEvent * ) override final;

//    bool hasTooltip = true;
private:
public:
    const std::string &getType() const {
        return type;
    }

    void setType(const std::string &type) {
        this->type = type;
    }

    const std::string &getName() const {
        return name;
    }

    void setName(const std::string &name) {
        this->name = name;
    }

    virtual std::string to_string() override;

private:
    std::shared_ptr<CGameObject> _clone();

    std::string type;
    std::string name;
    //TODO: tooltip
    //QGraphicsSimpleTextItem statsView;
    std::weak_ptr<CMap> map;
};


class Visitable {
public:
    virtual void onEnter(std::shared_ptr<CGameEvent>) = 0;

    virtual void onLeave(std::shared_ptr<CGameEvent>) = 0;
};

class Moveable {
public:
    virtual Coords getNextMove() = 0;

    virtual void beforeMove() = 0;

    virtual void afterMove() = 0;
};

class Wearable {
public:
    virtual void onEquip(std::shared_ptr<CGameEvent>) = 0;

    virtual void onUnequip(std::shared_ptr<CGameEvent>) = 0;
};

class Usable {
public:
    virtual void onUse(std::shared_ptr<CGameEvent>) = 0;
};

class Turnable {
public:
    virtual void onTurn(std::shared_ptr<CGameEvent>) = 0;
};

class Creatable {
public:
    virtual void onCreate(std::shared_ptr<CGameEvent>) = 0;

    virtual void onDestroy(std::shared_ptr<CGameEvent>) = 0;
};

