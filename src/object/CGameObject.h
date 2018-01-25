#pragma once

#include "core/CGlobal.h"
#include "core/CUtil.h"


class CGameEvent;

class CMap;

class CGame;

class CAnimation;

class CGameObject : public vstd::stringable, public std::enable_shared_from_this<CGameObject> {
V_META(CGameObject, vstd::meta::empty,
       V_PROPERTY(CGameObject, std::string, name, getName, setName),
       V_PROPERTY(CGameObject, std::string, type, getType, setType),
       V_PROPERTY(CGameObject, std::string, animation, getAnimation, setAnimation),
       V_PROPERTY(CGameObject, std::set<std::string>, tags, getTags, setTags)
)

public:
    static std::function<bool(std::shared_ptr<CGameObject>, std::shared_ptr<CGameObject>)> name_comparator;

    CGameObject();

    virtual ~CGameObject();

    std::shared_ptr<CMap> getMap();

    //TODO: get rid of game as a property!
    std::shared_ptr<CGame> getGame();

    void setGame(std::shared_ptr<CGame> game);

    template<typename T=CGameObject>
    std::shared_ptr<T> ptr() {
        //_cast purposedly
        return vstd::cast<T>(const_cast<CGameObject *>(this)->shared_from_this());
    }

    template<typename T>
    void setProperty(std::string name, T property) {
        this->meta()->set_property<CGameObject, T>(name, this->ptr(), property);
    }

    template<typename T>
    T getProperty(std::string name) {
        return this->meta()->get_property<CGameObject, T>(name, this->ptr());
    }

    void setStringProperty(std::string name, std::string value);

    void setBoolProperty(std::string name, bool value);

    void setNumericProperty(std::string name, int value);

    std::string getStringProperty(std::string name);

    bool getBoolProperty(std::string name);

    int getNumericProperty(std::string name);

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

    bool hasTag(std::string tag);

    void addTag(std::string tag);

    void removeTag(std::string tag);

public:
    std::string getType();

    void setType(std::string type);

    std::string getName();

    void setName(std::string name);

    virtual std::string to_string() override;

    std::set<std::string> getTags();

    void setTags(std::set<std::string> tags);

    std::string getAnimation();

    void setAnimation(std::string animation);

    std::shared_ptr<CAnimation> getAnimationObject();

private:
    std::shared_ptr<CGameObject> _clone();

    vstd::lazy<CAnimation> animationObject;

    std::string type;
    std::string name;
    std::string animation;

    std::set<std::string> tags;
    std::weak_ptr<CGame> game;
};


class Visitable {
public:
    virtual void onEnter(std::shared_ptr<CGameEvent>) = 0;

    virtual void onLeave(std::shared_ptr<CGameEvent>) = 0;
};

class Moveable {
public:

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

