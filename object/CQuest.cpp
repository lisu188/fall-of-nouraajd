#include "CQuest.h"

CQuest::CQuest() {
}

bool CQuest::isCompleted() {
	return false;
}

QString CQuest::getDescription() const {
	return description;
}

void CQuest::setDescription ( const QString &value ) {
	description = value;
}

