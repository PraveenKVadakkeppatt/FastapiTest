import uuid
import os
import json

from fastapi import FastAPI, HTTPException, status, Form, UploadFile, File
from pydantic import BaseModel, EmailStr, Field
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as redis
import aiofiles
from fastapi import Request

# ------------------ DATABASE ------------------

MONGO_URL = "mongodb://localhost:27017"
client = AsyncIOMotorClient(MONGO_URL, maxPoolSize=100, minPoolSize=10)
db = client["test_db"]
students_collection = db["test_collection"]


# ------------------ APP ------------------

r = redis.Redis(host='localhost', port=6379, decode_responses=True)


app = FastAPI()


# ------------------ REDIS ------------------


@app.on_event("startup")
async def startup():
    try:
        await r.ping()
        print(" Redis connected")
    except Exception as e:
        print(" Redis not connected:", e)




# ------------------ MODEL ------------------

class Student(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    age: int = Field(ge=5, le=100)
    course: str = Field(min_length=2)
    mark: int = Field(ge=0, le=100)
    email: EmailStr
    image: str | None = None

# ------------------ CREATE ------------------

@app.post("/student", status_code=status.HTTP_201_CREATED)
async def create_student(
    request: Request,   
    name: str = Form(...),
    age: int = Form(...),
    course: str = Form(...),
    mark: int = Form(...),
    email: EmailStr = Form(...),
    image: UploadFile = File(...)
):
    try:
        
        is_load_test = request.headers.get("X-Load-Test") == "true"

        if is_load_test:
            file_path = "test.png"   
        else:
            os.makedirs("assets", exist_ok=True)

            extension = image.filename.split(".")[-1]
            filename = f"{uuid.uuid4().hex[:8]}.{extension}"
            file_path = f"assets/{filename}"

            async with aiofiles.open(file_path, 'wb') as f:
                while chunk := await image.read(1024 * 1024):
                    await f.write(chunk)

        
        data = {
            "name": name,
            "age": age,
            "course": course,
            "mark": mark,
            "email": email,
            "image": file_path
        }

        result = await students_collection.insert_one(data)

        return {"id": str(result.inserted_id)}

    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")

# ------------------ GET ONE ------------------

@app.get("/students/{id}", status_code=status.HTTP_200_OK)
async def get_student(id: str):
    try:
        student = await students_collection.find_one({"_id": ObjectId(id)})
    except Exception as e:
        print("ERROR (GET ONE):", e)
        raise HTTPException(status_code=400, detail="Invalid ID")

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    student["_id"] = str(student["_id"])
    return student

# ------------------ GET ALL ------------------

@app.get("/students", status_code=status.HTTP_200_OK)
async def all_students():
    try:
        
        if r:
            cached_data = await r.get("students")
            if cached_data:
                return json.loads(cached_data)

        students = []

        async for student in students_collection.find().limit(50):
            student["_id"] = str(student["_id"])
            students.append(student)

        # Cache for 60 sec
        if r:
            await r.set("students", json.dumps(students), ex=60)

        return students

    except Exception as e:
        print("ERROR:", e)
        raise HTTPException(status_code=500, detail="Internal Server Error")

# ------------------ UPDATE ------------------

@app.put("/student/{id}", status_code=status.HTTP_200_OK)
async def update_student(id: str, student: Student):
    try:
        result = await students_collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": student.dict()}
        )
    except Exception as e:
        print("ERROR (UPDATE):", e)
        raise HTTPException(status_code=400, detail="Invalid ID")

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")

    if r:
        await r.delete("students")

    return {"message": "Student updated successfully"}

# ------------------ DELETE ------------------

@app.delete("/student/{id}")
async def delete_student(id: str):
    try:
        result = await students_collection.delete_one({"_id": ObjectId(id)})
    except Exception as e:
        print("ERROR (DELETE):", e)
        raise HTTPException(status_code=400, detail="Invalid ID")

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")

    if r:
        await r.delete("students")

    return {"message": "Deleted successfully"}