#include "CPathFinder.h"
#include "CTile.h"
#include <algorithm>
#include <cstdlib>


Coords CDumbPathFinder::findPath(CCreature *first, CCreature *second) {
  Coords current = first->getCoords();
  Coords goal = second->getCoords();
  if (current.z != goal.z) {
    return current;
  }
  int x = (goal.x > current.x) - (goal.x < current.x);
  int y = (goal.y > current.y) - (goal.y < current.y);
  if (x && first->getMap()
               ->getTile(current.x + x, current.y, current.z)
               ->canStep()) {
    return Coords(current.x + x, current.y, current.z);
  }
  if (y && first->getMap()
               ->getTile(current.x, current.y + y, current.z)
               ->canStep()) {
    return Coords(current.x, current.y + y, current.z);
  }
  return current;
}
Coords CRandomPathFinder::findPath(CCreature *first, CCreature *) {
  const int directions[4][2] = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
  int choice = rand() % 4;
  Coords current = first->getCoords();
  Coords next(current.x + directions[choice][0],
              current.y + directions[choice][1], current.z);
  return first->getMap()->getTile(next.x, next.y, next.z)->canStep() ? next
                                                                     : current;
}

std::list<Coords> CSmartPathFinder::getNearCells(Coords coords) {
  return {Coords(coords.x + 1, coords.y, coords.z),
          Coords(coords.x - 1, coords.y, coords.z),
          Coords(coords.x, coords.y + 1, coords.z),
          Coords(coords.x, coords.y - 1, coords.z)};
}
int CSmartPathFinder::getCost(Coords coords) {
  auto entry = values.find(coords);
  return entry == values.end() ? -1 : entry->second;
}
Coords CSmartPathFinder::getNearestCell(Coords start) {
  Coords best = start;
  int cost = getCost(start);
  for (Coords next : getNearCells(start)) {
    int candidate = getCost(next);
    if (candidate >= 0 && (cost < 0 || candidate < cost)) {
      best = next;
      cost = candidate;
    }
  }
  return best;
}
void CSmartPathFinder::processNode(
    CCreature *first, std::list<Cell> &nodes,
    std::unordered_set<Coords> &marked) {
  Cell cell = nodes.front();
  nodes.pop_front();
  Coords current = cell.toCoords();
  if (!marked.insert(current).second) {
    return;
  }
  auto bounds = first->getMap()->getBounds()[current.z];
  for (Coords next : getNearCells(current)) {
    if (next.x < 0 || next.y < 0 || next.x >= bounds.first ||
        next.y >= bounds.second ||
        !first->getMap()->getTile(next.x, next.y, next.z)->canStep()) {
      continue;
    }
    int cost = getCost(current) + 1;
    auto existing = values.find(next);
    if (existing == values.end() || cost < existing->second) {
      values[next] = cost;
      nodes.push_back(Cell(next.x, next.y, cell.goal));
    }
  }
}
Coords CSmartPathFinder::findPath(CCreature *first, CCreature *second) {
  Coords start = first->getCoords();
  Coords goal = second->getCoords();
  if (start.z != goal.z) {
    return start;
  }
  values.clear();
  values[goal] = 0;
  std::list<Cell> nodes{Cell(goal.x, goal.y, goal)};
  std::unordered_set<Coords> marked;
  while (!nodes.empty() && marked.find(start) == marked.end()) {
    processNode(first, nodes, marked);
  }
  return getNearestCell(start);
}

