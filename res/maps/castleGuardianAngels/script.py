# Long Live the Queen: shared registered behavior lives in plugins/castle_campaign.py.


def load(self, context):
    from game import CDialog
    from game import register

    CAMPAIGN_OUTCOMES = ("completed",)

    @register(context)
    class CastleGuardianAngelsOfficerDialog(CDialog):
        def reportProgress(self):
            self.getGame().getMap().getObjectByName("castleMission").reportProgress()
