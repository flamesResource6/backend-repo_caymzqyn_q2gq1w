import os
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime
from bson import ObjectId
from database import db, create_document, get_documents

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        try:
            return ObjectId(str(v))
        except Exception:
            raise ValueError("Invalid ObjectId")


class Template(BaseModel):
    name: str
    thumbnail: Optional[str] = Field(None, description="Data URL for preview thumbnail")
    data: Dict[str, Any] = Field(default_factory=dict, description="Full template JSON including background, elements, card size, dpi, bindings")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@app.get("/")
def read_root():
    return {"message": "ID Card Generator Backend Ready"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# Template Endpoints
@app.post("/api/templates", response_model=dict)
def create_template(template: Template):
    try:
        payload = template.model_dump()
        payload["created_at"] = datetime.utcnow()
        payload["updated_at"] = datetime.utcnow()
        inserted_id = create_document("template", payload)
        return {"id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/templates", response_model=List[dict])
def list_templates():
    try:
        docs = get_documents("template", {}, limit=None)
        # Convert ObjectId to string and strip _id key
        results = []
        for d in docs:
            d["id"] = str(d.get("_id"))
            d.pop("_id", None)
            results.append(d)
        # sort by updated_at desc
        results.sort(key=lambda x: x.get("updated_at") or datetime.min, reverse=True)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/templates/{template_id}", response_model=dict)
def get_template(template_id: str):
    try:
        doc = db["template"].find_one({"_id": ObjectId(template_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Template not found")
        doc["id"] = str(doc.get("_id"))
        doc.pop("_id", None)
        return doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/templates/{template_id}", response_model=dict)
def delete_template(template_id: str):
    try:
        res = db["template"].delete_one({"_id": ObjectId(template_id)})
        return {"deleted": res.deleted_count == 1}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Simple upload endpoint to store image as base64 data URL in DB (demo convenience)
@app.post("/api/uploads", response_model=dict)
async def upload_image(file: UploadFile = File(...)):
    try:
        content = await file.read()
        mime = file.content_type or "image/png"
        import base64
        data_url = f"data:{mime};base64,{base64.b64encode(content).decode()}"
        payload = {"name": file.filename, "data_url": data_url, "created_at": datetime.utcnow()}
        inserted_id = create_document("upload", payload)
        return {"id": inserted_id, "name": file.filename, "data_url": data_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
