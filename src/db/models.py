from datetime import datetime
from sqlalchemy import func, DateTime
from sqlmodel import Column, Field, Relationship, SQLModel
from typing import Optional
from uuid import UUID, uuid4

class Webpage(SQLModel, table=True):
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    parent_id: Optional[UUID] = Field(foreign_key='webpage.id')
    parent: Optional['Webpage'] = Relationship(
        back_populates='children',
        sa_relationship_kwargs={'remote_side': 'Webpage.id'},
    )
    children: list['Webpage'] = Relationship(back_populates='parent')
    html: str
    created_at: datetime = Field(sa_column=Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ))
