#include "Stats.h"

#include <QMetaProperty>
#include <sstream>

Stats::Stats() {
    for ( int i = 0; i < this->metaObject()->propertyCount(); i++ ) {
        QMetaProperty property = this->metaObject()->property ( i );
        this->setNumericProperty ( property.name(), 0 );
    }
}

Stats::Stats ( const Stats &stats ) {
	for ( int i = 0; i < this->metaObject()->propertyCount(); i++ ) {
		QMetaProperty property = this->metaObject()->property ( i );
        this->setNumericProperty ( property.name(), stats.getNumericProperty( property.name() ) );
	}
}

void Stats::operator=(const Stats &stats){
    for ( int i = 0; i < this->metaObject()->propertyCount(); i++ ) {
        QMetaProperty property = this->metaObject()->property ( i );
        this->setNumericProperty ( property.name(), stats.getNumericProperty( property.name() ) );
    }
}

void Stats::setMain ( QString stat ) {
    if ( stat[0] == 'A' ) {
        main = &agility;
	} else if ( stat[0] == 'I' ) {
		main = &intelligence;
	} else if ( stat[0] == 'S' ) {
		main = &strength;
	}
}

int Stats::getMain() {
	if ( !main ) {
		return 0;
	}
	return *main;
}

void Stats::addBonus ( Stats stats ) {
    for ( int i = 0; i < this->metaObject()->propertyCount(); i++ ) {
        QMetaProperty property = this->metaObject()->property ( i );
        this->incProperty ( property.name(), stats.getNumericProperty(property.name()) );
    }
}

void Stats::removeBonus ( Stats stats ) {
    for ( int i = 0; i < this->metaObject()->propertyCount(); i++ ) {
        QMetaProperty property = this->metaObject()->property ( i );
        this->incProperty ( property.name(), -stats.getNumericProperty(property.name()) );
    }
}

const char *Stats::getText ( int level ) {
	std::ostringstream stream;
	stream << "Level: " << level << "\n";
	stream << "Strength: " << strength << "\n";
	stream << "Agility: " << agility << "\n";
	stream << "Intelligence: " << intelligence << "\n";
	stream << "Stamina: " << stamina << "\n";
	stream << "Damage: " << dmgMin + damage << "-" << dmgMax + damage << "\n";
	stream << "Hit: " << hit + attack << "%"
	       << "\n";
	stream << "Crit: " << crit << "%"
	       << "\n";
	stream << "Armor: " << armor << "%"
	       << "\n";
	stream << "Block: " << block << "%"
	       << "\n";
	return stream.str().c_str();
}


Damage::Damage() {    for ( int i = 0; i < this->metaObject()->propertyCount(); i++ ) {
        QMetaProperty property = this->metaObject()->property ( i );
        this->setNumericProperty ( property.name(), 0 );
    }}

Damage::Damage ( const Damage &dmg ) {
    for ( int i = 0; i < this->metaObject()->propertyCount(); i++ ) {
        QMetaProperty property = this->metaObject()->property ( i );
        this->setNumericProperty ( property.name(), dmg.getNumericProperty( property.name() ) );
    }
}
