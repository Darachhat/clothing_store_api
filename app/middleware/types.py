from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AUTH_CONTEXT:
    system_code      : str
    client_id        : Optional[str] = None
    client_name      : Optional[str] = None
    auth_type        : Optional[str] = None
    channel          : Optional[str] = None
    is_authenticated : bool          = False
    permissions      : List[str]     = field(default_factory=list)

