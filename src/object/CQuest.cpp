#include "CQuest.h"

CQuest::CQuest() {
}

bool CQuest::isCompleted() {
    return false;
}

void CQuest::onComplete() {

}

void CQuest::setDescription(std::string description) {
    this->description = description;
}

std::string CQuest::getDescription() {
    return description;
}
