#include "CObjectHandler.h"
#include "CConfigurationProvider.h"
#include <QDirIterator>
#include "CMap.h"

CObjectHandler::CObjectHandler ( CMap *map ) :QObject ( map ) {
	this->map=map;
	QDirIterator dirIt ( "config/objects",QDirIterator::Subdirectories );
	while ( dirIt.hasNext() ) {
		dirIt.next();
		if ( QFileInfo ( dirIt.filePath() ).isFile() )
			if ( QFileInfo ( dirIt.filePath() ).suffix() == "json" ) {
				QString path=dirIt.filePath();
				QJsonObject config=CConfigurationProvider::getConfig ( path ).toObject();
				for ( auto it=config.begin(); it!=config.end(); it++ ) {
					objectConfig[it.key()]=it.value();
				}
			}
	}
}
