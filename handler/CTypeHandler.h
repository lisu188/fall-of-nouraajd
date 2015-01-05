#pragma once
#include <QObject>

class CGameObject;
class CObjectHandler;
class ATypeHandler : public QObject {
    Q_OBJECT
public:
    virtual CGameObject *create ( QString ) =0;
    virtual QString getHandlerName() =0;
protected:
    CObjectHandler *getObjectHandler();
};

class CTypeHandler : public ATypeHandler {
    Q_OBJECT
public:
    virtual CGameObject *create ( QString name ) override;
    virtual QString getHandlerName() override;
};

class PyTypeHandler : public ATypeHandler {
    Q_OBJECT
public:
    virtual CGameObject *create ( QString name ) override;
    virtual QString getHandlerName() override;
};
