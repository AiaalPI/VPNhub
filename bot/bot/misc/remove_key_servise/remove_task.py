from pydantic import BaseModel, Field


class TaskRemove(BaseModel):
    name_key: str = Field()
    key_id: int = Field()
    server_id: int = Field()
    wg_public_key: str = Field()
