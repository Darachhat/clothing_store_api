from typing import Any, Generic, List, Optional, Type, TypeVar
from sqlalchemy.orm import Session

from app.models import Base

ModelType = TypeVar("ModelType", bound=Base)


class BASE_SERVICE(Generic[ModelType]):
    """
    Abstract base service providing common database persistence methods.
    """
    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get_by_id(
        self
        , db : Session
        , id : Any
    ) -> Optional[ModelType]:
        return db.query(self.model).filter(self.model.id == id).first()

    def get_all(
        self
        , db    : Session
        , skip  : int = 0
        , limit : int = 100
    ) -> List[ModelType]:
        return db.query(self.model).offset(skip).limit(limit).all()

    def remove(
        self
        , db : Session
        , id : Any
    ) -> bool:
        obj = self.get_by_id(db=db, id=id)
        if obj:
            db.delete(obj)
            db.commit()
            return True
        return False

