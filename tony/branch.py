from shlex import quote
from .task import BaseTask
from .utils import beautify_results, CONSTANTS
from .broadcaster import Broadcaster

class BranchManagement(BaseTask):
    class BranchManager(BaseTask):

        CURRENT_BRANCH: str = "git branch --show-current"
        SWITCH_BRANCH: str = "git switch {}"
        LIST_BRANCH: str = "git branch -r"
        RESET_BRANCH: str = "git reset --hard origin/{}"

        def __init__(self, rBroadcaster: Broadcaster, sRelativePath: str, sFullPath: str = ""):
            super().__init__(rBroadcaster)
            self.sFullPath = "cd {}/{}".format(CONSTANTS["BASE_DIRECTORY"], sRelativePath) if len(sFullPath) == 0 else ("cd " + sFullPath)

        ## Walk into the directory and pull changes if required
        def prepare_directory(self, bDoNotUpdate: bool = False) -> None:
            self.lCommand = []
            self.lCommand.append((self.sFullPath, ""))
            if not bDoNotUpdate:
                self.lCommand.append(("git pull", "Pulling recent changes.."))

        ## Fetch current branch and return results
        async def get_current_branch(self, **kwargs) -> str:
            ## Walk directory
            self.prepare_directory(True)

            ## Fetch branch
            self.lCommand.append((self.CURRENT_BRANCH, "Checking the branch.."))

            await self.run(**kwargs)
            return self.lResults[1]

        ## Switch branch to provided by post
        async def switch_branch(self, sBranch: str, **kwargs) -> None:
            ## Walk directory
            self.prepare_directory(True)

            ## Reset branch
            self.lCommand.append((self.RESET_BRANCH.format(sBranch), "Resetting branch.."))

            ## Switch branch
            self.lCommand.append((self.SWITCH_BRANCH.format(sBranch), f"Switching branch to {quote(sBranch)}.."))
            await self.run(**kwargs)

            ## And now update it
            await self.update_repository(**kwargs)

        ## Return list of existing branches
        async def list_branch(self, **kwargs) -> str:
            ## Walk directory
            self.prepare_directory()

            ## List branches and return beautified results
            self.lCommand.append((self.LIST_BRANCH, "Fetching actual branches.."))
            await self.run(**kwargs)

            ## Beautify results
            self.lResults[1] = beautify_results(self.lResults[1])
            return self.lResults[1]

        async def update_repository(self, **kwargs) -> None:
            ## Get branch name
            sBranchName = await self.get_current_branch(bSilentCall = True)
            sBranchName = sBranchName.strip()

            ## Walk directory
            self.prepare_directory(True)

            ## Reset branch
            self.lCommand.append((self.RESET_BRANCH.format(sBranchName), f"Resetting branch {sBranchName}.."))

            ## Now update
            self.lCommand.append(("git pull", "Pulling recent changes.."))
            await self.run(**kwargs)

    def __init__(self, rBroadcaster: Broadcaster):
        super().__init__(rBroadcaster = rBroadcaster)

        ## Generate subclass objects for each type
        self.TASK_SUBCLASSES: dict = {
            "core" : (self.BranchManager(rBroadcaster, CONSTANTS["CORE_RELATIVE_PATH"]), ),
            "locale" : (self.BranchManager(rBroadcaster, CONSTANTS["LOCALE_RELATIVE_PATH"]), ),
            "patcher" : (self.BranchManager(rBroadcaster, "", CONSTANTS["PATCHER_ABSOLUTE_FILES_PATH"]), ),
            "all" : (self.BranchManager(rBroadcaster, CONSTANTS["CORE_RELATIVE_PATH"]), self.BranchManager(rBroadcaster, CONSTANTS["LOCALE_RELATIVE_PATH"]), self.BranchManager(rBroadcaster, "", CONSTANTS["PATCHER_ABSOLUTE_FILES_PATH"])),
        }

    def __del__(self):
        super().__del__()
        return

    ## Validate if provided class exists
    async def check_arguments(self, sType: str) -> bool:
        if not sType.lower() in self.TASK_SUBCLASSES:
            await self.rBroadcaster.send("Provided type doesn't exist!")
            await self.rBroadcaster.send("Available types: {}".format(", ".join(map(lambda key: key.lower(), self.TASK_SUBCLASSES.keys()))))
            return False

        return True

    ## List existing branches
    async def fetch_branch(self, sType: str, **kwargs) -> None:
        if await self.check_arguments(sType):
            for rClass in self.TASK_SUBCLASSES[sType.lower()]:
                try:
                    await rClass.list_branch(**kwargs)
                except Exception:
                    pass

                self.lResults = rClass.lResults
                return self.lResults[1]

    ## Change branch to provided by user
    async def change_branch(self, sType: str, sBranch: str, **kwargs) -> None:
        if await self.check_arguments(sType):
            for rClass in self.TASK_SUBCLASSES[sType.lower()]:
                try:
                    await rClass.switch_branch(sBranch, **kwargs)
                except Exception:
                    pass

                self.lResults = rClass.lResults

    ## Get running branch
    async def get_current_branch(self, sType: str, **kwargs) -> None:
        sBranch = ""
        if await self.check_arguments(sType):
            for rClass in self.TASK_SUBCLASSES[sType.lower()]:
                try:
                    sBranch = await rClass.get_current_branch(**kwargs)
                except Exception:
                    pass

                self.lResults = rClass.lResults

        return sBranch

    ## Pull recent changes to repository
    async def update_repository(self, sType: str, **kwargs) -> None:
        if await self.check_arguments(sType):
            for rClass in self.TASK_SUBCLASSES[sType.lower()]:
                try:
                    await rClass.update_repository(**kwargs)
                except Exception:
                    pass

                self.lResults = rClass.lResults
