#pragma once

#include "object/CItem.h"
#include "object/CGameObject.h"

class CSlot : public CGameObject {
V_META(CSlot, CGameObject,
       V_PROPERTY(CSlot, std::string, slotName, getSlotName, setSlotName),
       V_PROPERTY(CSlot, std::set<std::string>, types, getTypes, setTypes))
public:
    CSlot();

private:
    std::string slotName;
    std::set<std::string> types;
public:
    std::string getSlotName();

    void setSlotName(std::string slotName);

    std::set<std::string> getTypes();

    void setTypes(std::set<std::string> types);
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

    bool canFit(std::string slot, std::shared_ptr<CItem> item);
};


