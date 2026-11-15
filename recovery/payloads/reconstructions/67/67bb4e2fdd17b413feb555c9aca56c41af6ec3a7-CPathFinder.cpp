#include "CMap.h"
#include "CPathFinder.h"
#include "object/CObject.h"
#include <algorithm>
#include <cstdlib>

Coords CDumbPathFinder::findPath(CCreature *first, CCreature *second) {
    Coords start = first->getCoords(), goal = second->getCoords();
    std::list<Coords> nearby = {Coords(1, 0, 0), Coords(-1, 0, 0), Coords(0, 1, 0), Coords(0, -1, 0)};
    nearby.sort([&](Coords a, Coords b) {
        return Coords(start.x + a.x, start.y + a.y, start.z).getDist(goal) <
               Coords(start.x + b.x, start.y + b.y, start.z).getDist(goal);
    });
    for (Coords delta : nearby) {
        if (first->getMap()->canStep(start.x + delta.x, start.y + delta.y, start.z))
            return delta;
    }
    return Coords();
}
Coords CRandomPathFinder::findPath(CCreature *first, CCreature *) {
    Coords candidates[] = {Coords(1, 0, 0), Coords(-1, 0, 0), Coords(0, 1, 0), Coords(0, -1, 0), Coords()};
    Coords delta = candidates[std::rand() % 5], start = first->getCoords();
    return first->getMap()->canStep(start.x + delta.x, start.y + delta.y, start.z) ? delta : Coords();
}
int CSmartPathFinder::getCost(Coords coords) {
    auto found = values.find(coords);
    return found == values.end() ? -1 : found->second;
}
std::list<Coords> CSmartPathFinder::getNearCells(Coords coords) {
    return {Coords(coords.x - 1, coords.y, coords.z), Coords(coords.x + 1, coords.y, coords.z),
            Coords(coords.x, coords.y - 1, coords.z), Coords(coords.x, coords.y + 1, coords.z)};
}
Coords CSmartPathFinder::getNearestCell(Coords start) {
    Coords best = start;
    int cost = getCost(start);
    for (Coords next : getNearCells(start)) {
        int next_cost = getCost(next);
        if (next_cost >= 0 && (cost < 0 || next_cost < cost)) {
            best = next;
            cost = next_cost;
        }
    }
    return Coords(best.x - start.x, best.y - start.y, best.z - start.z);
}
void CSmartPathFinder::processNode(CCreature *first, std::list<Cell> &nodes, std::unordered_set<Coords> &marked) {
    Cell cell = nodes.front();
    nodes.pop_front();
    Coords current = cell.toCoords();
    if (!marked.insert(current).second)
        return;
    for (Coords next : getNearCells(current)) {
        if (!first->getMap()->canStep(next.x, next.y, next.z))
            continue;
        int next_cost = getCost(current) + 1;
        if (getCost(next) < 0 || next_cost < getCost(next)) {
            values[next] = next_cost;
            nodes.push_back(Cell(next.x, next.y, cell.goal));
        }
    }
}
Coords CSmartPathFinder::findPath(CCreature *first, CCreature *second) {
    Coords start = first->getCoords(), goal = second->getCoords();
    if (start.z != goal.z)
        return Coords();
    values.clear();
    values[goal] = 0;
    std::list<Cell> nodes = {Cell(goal.x, goal.y, goal)};
    std::unordered_set<Coords> marked;
    while (!nodes.empty() && !marked.count(start))
        processNode(first, nodes, marked);
    return getNearestCell(start);
}
