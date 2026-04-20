from pydantic import BaseModel


class ScanRequest(BaseModel):
    source_path: str
    recursive: bool = True


class CreateJobRequest(BaseModel):
    source_path: str
    recursive: bool = True
    profile: str = "balanced"

