from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="My API")


class Item(BaseModel):
    name: str
    value: str = ""


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/items")
def list_items():
    return []


@app.post("/items")
def create_item(item: Item):
    return {"id": 1, **item.dict()}
