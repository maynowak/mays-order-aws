"""
Command Result model for Installer Core
"""


class CommandStatus:
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RUNNING = "RUNNING"
    CANCELLED = "CANCELLED"


class CommandResult:
    def __init__(self, command: str, status: str, exit_code: int = 0,
                 stdout: str = "", stderr: str = "", error: str | None = None,
                 metadata: dict | None = None):
        self.command = command
        self.status = status
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.error = error
        self.metadata = metadata or {}

    @property
    def success(self) -> bool:
        return self.status == CommandStatus.SUCCESS

    @property
    def failed(self) -> bool:
        return self.status == CommandStatus.FAILED
