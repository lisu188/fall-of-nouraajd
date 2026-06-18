def load(self, context):
    from game import CBuilding
    from game import CEvent
    from game import Coords
    from game import register

    TRANSITION_GUARD = "multilevelTransitionGuard"
    ROUTE = (
        "1,1,0;2,1,0;3,1,0;4,1,0;4,1,1;5,1,1;6,1,1;6,2,1;6,3,1;6,4,1;4,1,1;4,1,0;5,1,0;6,1,0;6,2,0;6,3,0;6,4,0;6,5,0"
    )

    @register(context)
    class LevelStairs(CBuilding):
        def target(self):
            return Coords(
                self.getNumericProperty("targetX"),
                self.getNumericProperty("targetY"),
                self.getNumericProperty("targetZ"),
            )

        def publishWaypoint(self):
            game_map = self.getMap()
            target = self.target()
            if game_map and game_map.canStep(target):
                self.setBoolProperty("waypoint", True)
                self.setNumericProperty("x", target.x)
                self.setNumericProperty("y", target.y)
                self.setNumericProperty("z", target.z)
            else:
                self.setBoolProperty("waypoint", False)

        def onCreate(self, event):
            self.publishWaypoint()

        def onTurn(self, event):
            self.publishWaypoint()

        def onEnter(self, event):
            cause = event.getCause() if event else None
            if not cause or not cause.isPlayer():
                return
            if cause.getBoolProperty(TRANSITION_GUARD):
                cause.setBoolProperty(TRANSITION_GUARD, False)
                return

            game_map = self.getMap()
            target = self.target()
            if not game_map or not game_map.canStep(target):
                self.setBoolProperty("waypoint", False)
                return

            origin = self.getCoords()
            cause.setBoolProperty(TRANSITION_GUARD, True)
            cause.setCoords(target)
            game_map.setStringProperty("lastLevelTransition", self.getName())
            game_map.setNumericProperty(
                "levelTransitionCount",
                game_map.getNumericProperty("levelTransitionCount") + 1,
            )
            if target.z > origin.z:
                game_map.setBoolProperty("used_stairs_up", True)
            elif target.z < origin.z:
                game_map.setBoolProperty("used_stairs_down", True)

    @register(context)
    class MultilevelStart(CEvent):
        def onCreate(self, event):
            game_map = self.getMap()
            if game_map:
                game_map.setStringProperty("deterministicRoute", ROUTE)

        def onEnter(self, event):
            cause = event.getCause() if event else None
            if cause and cause.isPlayer():
                self.getMap().setBoolProperty("visited_multilevel_start", True)

    @register(context)
    class MultilevelGoal(CEvent):
        def onEnter(self, event):
            cause = event.getCause() if event else None
            if cause and cause.isPlayer():
                goal_id = "upper" if self.getCoords().z == 1 else "lower"
                self.getMap().setBoolProperty(f"visited_{goal_id}_goal", True)
