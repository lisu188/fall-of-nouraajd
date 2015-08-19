#include "controller/CTargetController.h"

CTargetController::CTargetController ( std::shared_ptr<CMapObject> target ) :target ( target ) {

}

std::shared_ptr<vstd::future<void>> CTargetController::control ( std::shared_ptr<CCreature> creature ) {
    return CSmartPathFinder::findNextStep ( creature->getCoords(),target->getCoords(),[creature] ( const Coords& coords ) {
        return creature->getMap()->canStep ( coords );
    } )->thenLater ( [creature] ( Coords coords ) {
        creature->moveTo ( coords );
    } );
}

