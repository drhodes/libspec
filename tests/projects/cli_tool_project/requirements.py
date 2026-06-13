from libspec.spec import Feature, SystemRequirement


class VersionControlFeature(Feature):
    """
    Version Control Feature
    """

    def date(self):
        return "2023-10-01"

    def description(self):
        return "Ability to version control the local files."


class GitInstallation(SystemRequirement):
    """
    System Requirement: Git must be installed on the host machine.
    """
