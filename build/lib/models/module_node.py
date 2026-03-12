from pydantic import BaseModel
from typing import List, Optional

class ModuleNode(BaseModel):
    """
    Type-safe Pydantic model for representing a Python module's structure for graph analysis.
    """
    path: str
    language: str
    imports: List[str]
    public_functions: List[str]
    classes: List[str]
    class_inheritance: Optional[dict] = None
