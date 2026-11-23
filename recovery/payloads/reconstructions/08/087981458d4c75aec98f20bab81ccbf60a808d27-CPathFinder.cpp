#include "CConfigurationProvider.h"
#include "CPathFinder.h"
#include "CTile.h"
#include <algorithm>
#include <cstdlib>

namespace {
bool mapTileCanStep(CMap *map, int x, int y, int z) {
  return CConfigurationProvider::getConfig("config/objects/tiles.json")
      .toObject()[map->getTile(x, y, z)]
      .toObject()["properties"]
      .toObject()["canStep"]
      .toBool();
}
} // namespace

CDumbPathFinder::CDumbPathFinder() {}
CDumbPathFinder::CDumbPathFinder(const CDumbPathFinder &) {}
CRandomPathFinder::CRandomPathFinder() {}
CRandomPathFinder::CRandomPathFinder(const CRandomPathFinder &) {}
CSmartPathFinder::CSmartPathFinder() {}
CSmartPathFinder::CSmartPathFinder(const CSmartPathFinder &) {}

Coords CDumbPathFinder::findPath(CCreature *first, CCreature *second) {
  Coords current = first->getCoords();
  Coords goal = second->getCoords();
  if (current.z != goal.z) {
    return current;
  }
  int x = (goal.x > current.x) - (goal.x < current.x);
  int y = (goal.y > current.y) - (goal.y < current.y);
  if (x &&
      mapTileCanStep(first->getMap(), current.x + x, current.y, current.z)) {
    return Coords(current.x + x, current.y, current.z);
  }
  if (y &&
      mapTileCanStep(first->getMap(), current.x, current.y + y, current.z)) {
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
  return mapTileCanStep(first->getMap(), next.x, next.y, next.z) ? next
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
    std::unordered_set<Coords, CoordsHasher> &marked) {
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
        !mapTileCanStep(first->getMap(), next.x, next.y, next.z)) {
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
  std::unordered_set<Coords, CoordsHasher> marked;
  while (!nodes.empty() && marked.find(start) == marked.end()) {
    processNode(first, nodes, marked);
  }
  return getNearestCell(start);
}

void CompletionListener::run() {
  if (started && !workers) {
    Q_EMIT completed();
  }
}
void CompletionListener::registerWorker() { ++workers; }
void CompletionListener::deregisterWorker() {
  if (workers) {
    --workers;
  }
  run();
}

PathFinderWorker::PathFinderWorker(CCreature *first, CCreature *second,
                                   APathFinder *finder)
    : first(first), second(second), finder(finder) {
  setAutoDelete(true);
  connect(this, SIGNAL(started()), CompletionListener::getInstance(),
          SLOT(registerWorker()));
  connect(this, SIGNAL(ended()), CompletionListener::getInstance(),
          SLOT(deregisterWorker()));
  connect(this, SIGNAL(completed(int, int)), first, SLOT(move(int, int)));
  Q_EMIT started();
}
void PathFinderWorker::run() {
  Coords next = finder->findPath(first, second);
  Q_EMIT completed(next.x - first->getPosX(), next.y - first->getPosY());
  Q_EMIT ended();
  finder->deleteLater();
}

bool CSmartPathFinder::canStep(CMap *map, int x, int y, int z) {
  return mapTileCanStep(map, x, y, z);
}
