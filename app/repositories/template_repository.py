from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.template import Template


class TemplateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_name(self, name: str) -> Template | None:
        return self.db.scalar(select(Template).where(Template.name == name))

    def list(self) -> list[Template]:
        return list(self.db.scalars(select(Template).order_by(Template.name)))

    def save(self, template: Template) -> Template:
        self.db.add(template)
        self.db.commit()
        return template

    def delete(self, template: Template) -> None:
        self.db.delete(template)
        self.db.commit()
