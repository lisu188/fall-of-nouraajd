#pragma once

class CMouseHandler;

class CClickAction {
public:
	virtual void onClickAction ( CMouseHandler *object ) =0;
};

class CMouseHandler {
public:
	static void handleClick ( CMouseHandler *object );
	virtual CClickAction *getClickAction() =0;
};
