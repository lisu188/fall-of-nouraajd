#include "dumbpathfinder.h"

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
