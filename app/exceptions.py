from __future__ import annotations


class AssignmentConflictError(Exception):
    def __init__(self, message: str, batch) -> None:
        super().__init__(message)
        self.message = message
        self.batch = batch


class MappingNotFoundError(Exception):
    pass


class BitrixSyncConfigurationError(Exception):
    pass

