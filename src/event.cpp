#include "event.h"
#include "scriptmanager.h"

Event::Event() {}

Event::Event ( const Event & ) {}

void Event::onEnter() {
	if ( this->isEnabled() ) {
		map->getEngine()->executeScript ( script );
	}
}

void Event::onMove() {}

void Event::loadFromJson ( std::string name ) {}
QString Event::getScript() const { return script; }

void Event::setScript ( const QString &value ) { script = value; }

bool Event::isEnabled() { return enabled; }

void Event::setEnabled ( bool enabled ) { this->enabled = enabled; }
