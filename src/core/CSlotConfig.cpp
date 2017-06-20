

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
