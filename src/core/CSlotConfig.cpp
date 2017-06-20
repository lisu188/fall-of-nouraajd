

#include "CSlotConfig.h"

CSlotConfig::CSlotConfig() {

}

CSlotMap CSlotConfig::getConfiguration() {
    return configuration;
}

void CSlotConfig::setConfiguration(CSlotMap configuration) {
    CSlotConfig::configuration = configuration;
}

CSlot::CSlot() {

}

std::string CSlot::getSlotName() {
    return slotName;
}

void CSlot::setSlotName(std::string slotName) {
    CSlot::slotName = slotName;
}

std::set<std::string> CSlot::getTypes() {
    return types;
}

void CSlot::setTypes(std::set<std::string> types) {
    CSlot::types = types;
}
