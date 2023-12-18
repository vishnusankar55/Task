from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Form
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from pydantic import BaseModel

DATABASE_URL_POSTGRES = "postgresql://user:password@localhost/dbname"

Base = declarative_base()

# Define Users model
class Users(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    phone = Column(String, unique=True, index=True)
    profile = relationship("Profile", back_populates="user")

# Define Profile model
class Profile(Base):
    __tablename__ = "profile"
    id = Column(Integer, primary_key=True, index=True)
    profile_picture = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("Users", back_populates="profile")

# Create PostgreSQL engine and session
engine_postgres = create_engine(DATABASE_URL_POSTGRES)
SessionPostgres = sessionmaker(autocommit=False, autoflush=False, bind=engine_postgres)

app = FastAPI()

# Dependency to get PostgreSQL database session
def get_db_postgres():
    db = SessionPostgres()
    try:
        yield db
    finally:
        db.close()

# Create tables
Base.metadata.create_all(bind=engine_postgres)

# Create user in PostgreSQL
@app.post("/register")
async def register(
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    phone: str = Form(...),
    profile_picture: UploadFile = File(None),
    db_postgres: SessionPostgres = Depends(get_db_postgres),
):
    # Check if email or phone already exists
    if db_postgres.query(Users).filter(Users.email == email).first() or \
            db_postgres.query(Users).filter(Users.phone == phone).first():
        raise HTTPException(status_code=400, detail="Email or phone already registered")

    # Save user details to Users table
    user = Users(full_name=full_name, email=email, password=password, phone=phone)
    db_postgres.add(user)
    db_postgres.commit()
    db_postgres.refresh(user)

    # Save profile picture to Profile table
    if profile_picture:
        profile_picture_content = await profile_picture.read()
        profile_picture_str = profile_picture_content.decode("utf-8")
        profile = Profile(profile_picture=profile_picture_str, user_id=user.id)
        db_postgres.add(profile)
        db_postgres.commit()
        db_postgres.refresh(profile)

    return {"message": "User registered successfully"}

# Get user details by user_id from both tables
@app.get("/user/{user_id}")
async def get_user_details(
    user_id: int,
    db_postgres: SessionPostgres = Depends(get_db_postgres),
):
    # Get user details from Users table
    user = db_postgres.query(Users).filter(Users.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get profile picture from Profile table
    profile = db_postgres.query(Profile).filter(Profile.user_id == user.id).first()

    return {
        "user_id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "profile_picture": profile.profile_picture if profile else None
    }
