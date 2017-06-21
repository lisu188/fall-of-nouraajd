

#include "CSlotConfig.h"

CSlotConfig::CSlotConfig() {

}

CSlotMap CSlotConfig::getConfiguration() {
    return configuration;
}

void CSlotConfig::setConfiguration(CSlotMap configuration) {
    CSlotConfig::configuration = configuration;
}

bool CSlotConfig::canFit(std::string slot, std::shared_ptr<CItem> item) {
    auto types = configuration.find(slot)->second->getTypes();
    for (auto type : types) {
        if (item->meta()->inherits(type)) {
            return true;
        }
    }
    return false;
}

std::set<std::string> CSlotConfig::getFittingSlots(std::shared_ptr<CItem> item) {
    std::set<std::string> ret;
    for (auto it : configuration) {
        if (canFit(it.first, item)) {
            ret.insert(it.first);
        }
    }
    return ret;
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
