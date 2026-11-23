#include "pathfinder.h"
#include <QDebug>
#include <math.h>
#include <src/gamescene.h>
#include <src/configurationprovider.h>

PathFinder::PathFinder() {
}


DumbPathFinder::DumbPathFinder() {
	
}

DumbPathFinder::DumbPathFinder(const DumbPathFinder&) {
}

Coords DumbPathFinder::findPath(Coords start, Coords goal) {
	int px = goal.x;
	int py = goal.y;
	int dirx = px - start.x;
	int diry = py - start.y;
	int movx, movy;
	if (dirx > 0) {
		movx = 1;
	}
	else if (dirx == 0) {
		movx = 0;
	}
	else {
		movx = -1;
	}
	if (diry > 0) {
		movy = 1;
	}
	else if (diry == 0) {
		movy = 0;
	}
	else {
		movy = -1;
	}
	if (movx != 0 && movy != 0) {
		switch (rand() % 2) {
			case 0:
				movx = 0;
				break;
			case 1:
				movy = 0;
				break;
		}
	}
	return Coords(movx, movy, 0);
}


RandomPathFinder::RandomPathFinder() {
	
}

RandomPathFinder::RandomPathFinder(const RandomPathFinder &) {
}

Coords RandomPathFinder::findPath(Coords, Coords) {
	int a = rand() % 3 - 1;
	int b = rand() % 3 - 1;
	return Coords(a, b, 0);
}



SmartPathFinder::SmartPathFinder() {
}

SmartPathFinder::SmartPathFinder(const SmartPathFinder &) {
	
}

Coords SmartPathFinder::findPath(Coords start, Coords goal) {
	if (start.z != goal.z) {
		qDebug() << "Changing Level Not Supported Yet.";
		throw new std::exception();
	}
	class Cell {
		public:
			int x, y;
			Coords goal;
			Cell(int x, int y, Coords goal)
					: x(x), y(y), goal(goal) {
			}
	};
	class CellCompare {
		public:
			bool operator()(const Cell &a, const Cell &b) {
				int dista = sqrt(
						(a.x - a.goal.x) * (a.x - a.goal.x)
								+ (a.y - a.goal.y) * (a.y - a.goal.y));
				int distb = sqrt(
						(b.x - b.goal.x) * (b.x - b.goal.x)
								+ (b.y - b.goal.y) * (b.y - b.goal.y));
				if (dista != distb)
					return dista < distb;
				if (a.x != b.x)
					return a.x < b.x;
				return a.y < b.y;
			}
	};
	std::set<Cell, CellCompare> nodes;
	std::set<Cell, CellCompare> marked;
	std::map<Cell, int, CellCompare> values;
	int level = start.z;
	nodes.insert(Cell(goal.x, goal.y, start));
	values.insert(std::pair<Cell, int>(Cell(goal.x, goal.y, start), 0));
	Map *map = GameScene::getGame()->getMap();
	while (!nodes.empty()) {
		Cell currentCell = *nodes.begin();
		nodes.erase(nodes.begin());
		if (currentCell.x == currentCell.goal.x
				&& currentCell.y == currentCell.goal.y) {
			break;
		}
		if (marked.find(currentCell) != marked.end()) {
			continue;
		}
		int curValue = (*values.find(currentCell)).second;
		
		for (int i = -1; i <= 1; i++)
			for (int j = -1; j <= 1; j++) {
				if (i != 0 && j != 0)
					continue;
				if (i == 0 && j == 0)
					continue;
				Cell tmpCell(currentCell.x + i, currentCell.y + j, start);
				bool canStep = (*ConfigurationProvider::getConfig(
						"config/tiles.json"))[map->getTile(tmpCell.x, tmpCell.y,
						level)].get("canStep", true).asBool();
				if (!canStep) {
					continue;
				}
				if (values.find(tmpCell) != values.end()) {
					int tmpValue = (*values.find(tmpCell)).second;
					if (tmpValue >= curValue + 1) {
						values.erase(values.find(tmpCell));
						values.insert(
								std::pair<Cell, int>(tmpCell, curValue + 1));
					}
				}
				else {
					values.insert(std::pair<Cell, int>(tmpCell, curValue + 1));
				}
				nodes.insert(tmpCell);
			}
		marked.insert(currentCell);
	}
	std::list<Cell> list;
	for (int i = -1; i <= 1; i++)
		for (int j = -1; j <= 1; j++) {
			if (i != 0 && j != 0)
				continue;
			if (i == 0 && j == 0)
				continue;
			if (values.find(Cell(start.x + i, start.y + j, start))
					!= values.end()) {
				list.push_back(Cell(start.x + i, start.y + j, start));
			}
		}
	if (list.size() == 0) {
		DumbPathFinder finder;
		return finder.findPath(start, goal);
	}
	int cost = (*values.find(*list.begin())).second;
	Cell target = (*values.find(*list.begin())).first;
	for (std::list<Cell>::iterator it = list.begin(); it != list.end(); it++) {
		int tmpCost = (*values.find(*it)).second;
		if (tmpCost < cost) {
			cost = tmpCost;
			target = (*values.find(*it)).first;
		}
	}
	return Coords(target.x - start.x, target.y - start.y, 0);
}



PathFinderWorker::PathFinderWorker(Creature *creature, PathFinder *finder) : creature(creature), finder(finder) {
    setAutoDelete(true);
    connect(this, SIGNAL(completed(int,int)), creature, SLOT(move(int,int)));
    connect(this, SIGNAL(started()), CompletionListener::getInstance(), SLOT(registerWorker()));
    connect(this, SIGNAL(ended()), CompletionListener::getInstance(), SLOT(deregisterWorker()));
    Q_EMIT started();
}
void PathFinderWorker::run() {
    Coords delta = finder->findPath(creature->getCoords(), GameScene::getPlayer()->getCoords());
    Q_EMIT completed(delta.x, delta.y);
    Q_EMIT ended();
    finder->deleteLater();
}

void CompletionListener::run() {
    if (started && workers == 0) {
        started = false;
        Q_EMIT completed();
    }
}
void CompletionListener::registerWorker() { ++workers; }
void CompletionListener::deregisterWorker() {
    if (workers > 0) --workers;
    run();
}
