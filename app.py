from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Form
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

DATABASE_URL_POSTGRES = "postgresql://user:password@localhost/dbname"
DATABASE_URL_MONGO = "mongodb://localhost:27017"

Base = declarative_base()

class UserPostgres(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    phone = Column(String)

engine_postgres = create_engine(DATABASE_URL_POSTGRES)
SessionPostgres = sessionmaker(autocommit=False, autoflush=False, bind=engine_postgres)

class UserProfileMongo(BaseModel):
    full_name: str
    profile_picture: str

client_mongo = AsyncIOMotorClient(DATABASE_URL_MONGO)
db_mongo = client_mongo.get_database()

app = FastAPI()

def get_db_postgres():
    db = SessionPostgres()
    try:
        yield db
    finally:
        db.close()

async def get_db_mongo():
    try:
        yield db_mongo
    finally:
        client_mongo.close()

@app.post("/register")
async def register(
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    phone: str = Form(...),
    profile_picture: UploadFile = File(None),
    db_postgres: SessionPostgres = Depends(get_db_postgres),
    db_mongo: AsyncIOMotorClient = Depends(get_db_mongo)
):
    if db_postgres.query(UserPostgres).filter(UserPostgres.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user_postgres = UserPostgres(full_name=full_name, email=email, password=password, phone=phone)
    db_postgres.add(user_postgres)
    db_postgres.commit()
    db_postgres.refresh(user_postgres)

    if profile_picture:
        profile_picture_content = await profile_picture.read()
        profile_picture_str = profile_picture_content.decode("utf-8")
        user_mongo = UserProfileMongo(full_name=full_name, profile_picture=profile_picture_str)
        await db_mongo.users.insert_one(user_mongo.dict())

    return {"message": "User registered successfully"}


@app.get("/user/{user_id}")
async def get_user_details(
    user_id: int,
    db_postgres: SessionPostgres = Depends(get_db_postgres),
    db_mongo: AsyncIOMotorClient = Depends(get_db_mongo)
):
    user_postgres = db_postgres.query(UserPostgres).filter(UserPostgres.id == user_id).first()
    if not user_postgres:
        raise HTTPException(status_code=404, detail="User not found")

    user_mongo = await db_mongo.users.find_one({"full_name": user_postgres.full_name})
    if not user_mongo:
        raise HTTPException(status_code=404, detail="User not found in MongoDB")

    return {
        "user_id": user_postgres.id,
        "full_name": user_postgres.full_name,
        "email": user_postgres.email,
        "phone": user_postgres.phone,
        "profile_picture": user_mongo.get("profile_picture", None)
    }

