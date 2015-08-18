#include "controller/CTargetController.h"

CTargetController::CTargetController(std::shared_ptr<CMapObject> target):target(target){

}

void CTargetController::control(std::shared_ptr<CCreature> creature){
    std::shared_ptr<CMap> map=creature->getMap();
    CSmartPathFinder::findNextStep ( creature->getCoords(),target->getCoords(),[map] ( const Coords& coords ) {
            return map->canStep ( coords );
        } );
}

