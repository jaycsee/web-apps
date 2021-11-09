import logging
from types import ModuleType
from typing import Awaitable, NoReturn
import importlib
import traceback
import os
import sys
import asyncio
import random
import multiprocessing
import multiprocessing.connection

assert sys.version_info >= (3, 9) # Must be using Python 3.9 or later

# 3.10 changes: replace union/optional with |, use the match keyword, replace str types iwth real types

def _deploy(moduleName: str, deploymentPipe: "DeploymentManagerPipe", arguments: str) -> NoReturn:
    import importlib 
    import time
    import sys
    import asyncio

    async def autoFlush():
        while True:
            await asyncio.sleep(1)
            sys.stdout.flush()
            deploymentPipe.checkForResponses()

    importlib.import_module(moduleName)
    asyncio.get_event_loop()
    asyncio.ensure_future(autoFlush())
    importlib.import_module(moduleName + ".deploy").Deployment(deploymentPipe, arguments).deploy()
    deploymentPipe.stop()
    while True: time.sleep(10)

class DeploymentCommand:
    """Data class that carries a command meant to be interpreted by the deployment manager"""

    def __init__(self, authority: str, messageID: str, command: str, arguments: str):
        self.authority = authority
        self.messageID = messageID
        self.command = command
        self.arguments = arguments
        self.response = None
        self.responseFuture = None

    def setResponse(self, response: "DeploymentCommand") -> None:
        self.response = response
        if self.responseFuture: self.responseFuture.set_result(response)

    async def response(self) -> Awaitable["DeploymentCommand"]:
        if not self.responseFuture: self.responseFuture = asyncio.get_event_loop().create_future()
        if self.response: self.responseFuture.set_result(self.response)
        return self.responseFuture

class DeploymentManagerPipe:
    """Class that provides a skeleton of DeploymentManager that can be given to the deployment to access methods in the main DeploymentManager."""
    def __init__(self, deploymentID: str, pipe: multiprocessing.connection.Connection):
        self.deploymentID = deploymentID
        self.pipe = pipe
        self.stopped = False
        self.messages = {} # type: dict[str, DeploymentCommand]

    def signalRunning(self) -> DeploymentCommand:
        """Signals that the deployment has sucessfully initiated and is running. This must be called after successful initiation, otherwise risking process cleanup and termination."""
        return self.sendDeploymentCommand("running", self.deploymentID)

    def queueFullUpdate(self) -> DeploymentCommand:
        """Signals that the deployment should be updated after shutdown"""
        return self.sendDeploymentCommand("update", self.deploymentID)

    def queueRestart(self) -> DeploymentCommand:
        """Signals that the deployment should be restarted after shutdown"""
        return self.sendDeploymentCommand("restart", self.deploymentID)
    
    def reload(self, deployment, module: str) -> bool:
        """Reloads and updates a module of the deployment. This is generally passed through to the object."""
        return deployment.reload(module)
    
    def log(self, message: str) -> DeploymentCommand:
        """Sends a log message to the deployment manager"""
        return self.sendDeploymentCommand("log", message)

    def stop(self) -> DeploymentCommand:
        """Signals that the deployment has stopped and can safely be terminated."""
        if self.stopped: return None
        ret = self.sendDeploymentCommand("stop", self.deploymentID)
        self.stopped = True
        return ret

    def sendDeploymentCommand(self, command: str, arguments: str) -> DeploymentCommand:
        """Sends a deployment command to the deployment manager"""
        if self.stopped: raise ValueError(f"This deployment '{self.deploymentID}' has stoped. Further commands through this deployment are not accepted.") 
        while messageID := ''.join(random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(8)) in self.messages: pass
        self.messages[messageID] = DeploymentCommand(self.deploymentID, messageID, command, arguments)
        self.pipe.send(self.messages[messageID])
        return self.messages[messageID]

    def checkForResponses(self) -> None:
        """Checks for the responses to sent deployment commands"""
        while self.pipe.poll():
            if (x := self.pipe.recv()).id in self.messageIDs: self.message[x.id].setResponse(x)

class DeploymentManager:
    """Class to manage deployments and update its modules"""

    def __init__(self) -> None:
        self.deploymentProcesses = {} # type: dict[str, multiprocessing.Process]
        self.deploymentConnections = {} # type: dict[str, multiprocessing.connection.Connection]

        self.modules = {} # type: dict[str, ModuleType]
        self.moduleNames = {} # type: dict[str, str]
        self.arguments = {} # type: dict[str, str]

        self.startingDeployments = set() # type: set[str]
        self.activeDeployments = set() # type: set[str]
        self.update = set() # type: set[str]
        self.restart = set() # type: set[str]

    async def deploy(self, file: str, arguments: str, timeout: int=30, id: str=None) -> bool:
        """Deploys with a given argument, folder and timeout. The folder must contain the file 'deploy.py' with the class 'Deployment'. It must implment the methods 'deploy', 'update', and 'shutdown'. This is a blocking call that returns whether the it has been fully loaded and is running, indicated by the 'running' field. If it fails, it is cleaned up."""
        if id is None: id = ''.join(random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(16))
        while id in self.activeDeployments or id in self.startingDeployments: id = ''.join(random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(16))
        self.startingDeployments.add(id)
        try:
            print(f"Deploying '{file}' with arguments '{arguments}'")

            m = importlib.import_module(file + ".deploy") 
            managerConnection, deploymentConnection = multiprocessing.Pipe(True)
            deploymentPipe = DeploymentManagerPipe(id, deploymentConnection)

            process = multiprocessing.Process(target=_deploy, args=(file, deploymentPipe, arguments))
            process.start()

            done = False
            for x in range(timeout):
                await asyncio.sleep(1)
                if managerConnection.poll():
                    try:
                        if (x := managerConnection.recv()).command == "running" and x.arguments == id: 
                            done = True
                            break
                    except Exception: pass
            
            self.startingDeployments.discard(id)
            self.update.discard(id)
            self.restart.discard(id)

            if done: 
                self.deploymentProcesses[id] = process
                self.deploymentConnections[id] = managerConnection
                self.modules[id] = m
                self.moduleNames[id] = file
                self.arguments[id] = arguments
                print(f"Deployed '{file}' successfully")
                self.activeDeployments.add(id)
                return True
            else: 
                process.terminate()
                await asyncio.sleep(3)
                process.kill()
                await asyncio.sleep(1)
                process.close()
                del process
                print(f"Deploying '{file}' failed: Timed out")
                return False
        except Exception: 
            print(f"Deployment '{file}' failed:\n")
            traceback.print_exc()
            print("\n")
        return False

    async def stop(self, deploymentID) -> None:
        """Stops a given deployment id and restarts it if it has been queued"""
        if deploymentID not in self.deploymentProcesses: return
        self.activeDeployments.discard(deploymentID)
        self.deploymentProcesses[deploymentID].terminate()
        await asyncio.sleep(3)
        self.deploymentProcesses[deploymentID].kill()
        await asyncio.sleep(1)
        self.deploymentProcesses[deploymentID].close()
        del self.deploymentProcesses[deploymentID]
        del self.deploymentConnections[deploymentID]

        if deploymentID in self.update: importlib.reload(self.modules[deploymentID])
        if deploymentID in self.restart: 
            x = await self.deploy(self.moduleNames[deploymentID], self.arguments[deploymentID], id=deploymentID)
            if not x: print(f"Failed redeployment of '{self.moduleNames[deploymentID]}' with id '{deploymentID}' and arguments '{self.arguments[deploymentID]}'")
    
    def queueFullUpdate(self, deploymentID) -> None:
        """Signals that the deployment should be updated after shutdown"""
        self.update.add(deploymentID)

    def queueRestart(self, deploymentID) -> None:
        """Signals that the deployment should be restarted after shutdown"""
        self.restart.add(deploymentID)

    async def run(self):
        """Runs the deployment manager"""
        print("Initializing deployment manager...")
        s = await self.deploy("discordbot", "master", timeout=60)
        if not s: 
            print("Failed the main deployment. Terminating.")
            os._exit(1)
        while True:
            await asyncio.sleep(3)

            if len(self.activeDeployments) == 0 and len(self.startingDeployments) == 0 and len(self.restart) == 0: 
                print("All deployments have terminated. Exiting...")
                exit(0)

            stopProcess = None
            for k in self.activeDeployments:
                if stopProcess: break
                c = self.deploymentConnections[k]
                while c.poll():
                    try:
                        m = c.recv() # type: DeploymentCommand
                        responseData = ""
                        if m.command == "stop": stopProcess = m.arguments
                        elif m.command == "update": self.queueFullUpdate(m.arguments)
                        elif m.command == "restart": self.queueRestart(m.arguments)
                        elif m.command == "log": print(f"{m.authority}: {m.arguments}")
                        elif m.command == "list": responseData = str(self.moduleNames)
                        c.send(DeploymentCommand("manager", m.id, "OK", responseData))
                    except Exception: pass
            if stopProcess is None: continue
            
            print(f"Deployment of '{self.moduleNames[stopProcess]}' with id '{stopProcess}' and arguments '{self.arguments[stopProcess]}' has ended." + ("" if stopProcess not in self.restart else " A restart has been queued."))

            asyncio.ensure_future(self.stop(stopProcess))
            self.activeDeployments.discard(stopProcess)

if __name__ == '__main__':
    manager = DeploymentManager()
    eventloop = asyncio.get_event_loop()
    multiprocessing.log_to_stderr(logging.INFO)
    multiprocessing.set_start_method("spawn")
    asyncio.run(manager.run())