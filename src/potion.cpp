#include "potion.h"
#include <QDebug>
#include "CConfigurationProvider.h"
#include <src/creature.h>
#include <src/gamescene.h>

Potion::Potion() {}

Potion::Potion ( const Potion & ) {}

void Potion::onUse ( Creature *creature ) {
	qDebug() << creature->typeName.c_str() << "used" << typeName.c_str();
	effect ( creature, power );
}

void Potion::loadFromJson ( std::string name ) {
	Item::loadFromJson ( name );
	if ( ( std::string ( typeName ).find ( "LifePotion" ) != std::string::npos ) ) {
		effect = &LifeEffect;
	} else if ( std::string ( typeName ).find ( "ManaPotion" ) != std::string::npos ) {
		effect = &ManaEffect;
	}
}

void LifeEffect ( Creature *creature, int power ) {
	creature->healProc ( power * 20 );
}

void ManaEffect ( Creature *creature, int power ) {
	creature->addManaProc ( power * 20 );
}
