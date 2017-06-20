#pragma once

#include "object/CGameObject.h"

class CSlot : public CGameObject {
V_META(CSlot, CGameObject, vstd::meta::empty())
public:
    CSlot();
};

typedef std::map<std::string, std::shared_ptr<CSlot> > CSlotMap;

class CSlotConfig : public CGameObject {
V_META(CSlotConfig, CGameObject,
       V_PROPERTY(CSlotConfig, CSlotMap, configuration, getConfiguration, setConfiguration))
public:
    CSlotConfig();

private:
    CSlotMap configuration;
public:
    CSlotMap getConfiguration();

    void setConfiguration(CSlotMap configuration);
};


