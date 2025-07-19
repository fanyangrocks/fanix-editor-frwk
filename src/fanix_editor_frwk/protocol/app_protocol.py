from typing import Protocol
from typing import runtime_checkable


@runtime_checkable
class AppProtocol(Protocol):
    def exec_(self, /) -> int: ...
