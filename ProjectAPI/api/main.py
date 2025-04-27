from fastapi import FastAPI, HTTPException, Depends, Body, status, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi import Body 
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.delete_api import DeleteApi
from pydantic import BaseModel, EmailStr
import pytz
from sqlalchemy import or_
from passlib.context import CryptContext
from datetime import datetime, timedelta
import uuid
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# from models import *
# from database import *

from api.models import *
from api.database import *

load_dotenv()

INFLUXDB_URL = os.getenv("INFLUXDB_URL")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET")

write_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
write_api = write_client.write_api(write_options=SYNCHRONOUS)
query_api = write_client.query_api()
delete_api = DeleteApi(write_client)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    username: str
    email: str
    phone: str
    password: str

class airquality(BaseModel):
    node_id: str
    PM1: float
    PM2_5: float
    PM4: float
    PM10: float
    CO2: float
    temperature: float
    humidity: float

class LoginRequest(BaseModel):
    username_or_email: str
    password: str

class NodeRequest(BaseModel):
    node_id: str
    node_name: str
    location: str
    description: str
    user_id: int

app = FastAPI(
    title="API AirQuality",
    description='',
    root_path="/eng.rmuti"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
def send_verification_email(email: str, token: str):
    msg = MIMEMultipart()
    msg['From'] = "game38384@gmail.com"
    msg['To'] = email
    msg['Subject'] = "กรุณายืนยันอีเมลของคุณ"

    body = f"กรุณาคลิกลิงก์นี้เพื่อยืนยันอีเมลของคุณ: http://localhost:8000/verify-email?token={token}"
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()

        server.login("game38384@gmail.com", "dcqi heuu mbvn ukkx")

        server.sendmail("game38384@gmail.com", email, msg.as_string())
        server.quit()
        print("Email sent successfully!")
        
    except Exception as e:
        print(f"Error sending email: {e}")

@app.post("/aqi", tags=["InfluxDB Data API"])
async def airquality(data: airquality):
    try:
        point = {
            "measurement": "air_quality",
            "tags": {
                "node_id": data.node_id,
            },
            "fields": {
                "PM1": data.PM1,
                "PM2_5": data.PM2_5,
                "PM4": data.PM4,
                "PM10": data.PM10,
                "CO2": data.CO2,
                "temperature": data.temperature,
                "humidity": data.humidity
            }
        }
        write_api.write(bucket=INFLUXDB_BUCKET, record=point)
        return {
            "status": 1,
            "message": "Data successfully written",
            "data": data
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={ "status": 0, "message": str(e), "data": {} }
        )

@app.get("/aqi", tags=["InfluxDB Data API"])
async def get_data(node_id: str):
    try:
        query = f"""
            from(bucket: "{INFLUXDB_BUCKET}") 
                |> range(start: -1h) 
                |> filter(fn: (r) => r.node_id == "{node_id}")
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
            """
        result = query_api.query(org=INFLUXDB_ORG, query=query)
        data = []
        for table in result:
            for record in table.records:
                data.append({
                    "node_id": record.values.get("node_id"),
                    "PM1": record.values.get("PM1"),
                    "PM2_5": record.values.get("PM2_5"),
                    "PM4": record.values.get("PM4"),
                    "PM10": record.values.get("PM10"),
                    "CO2": record.values.get("CO2"),
                    "temperature": record.values.get("temperature"),
                    "humidity": record.values.get("humidity"),
                    "time": record.get_time().astimezone(pytz.timezone("Asia/Bangkok"))
                })
        return {
            "status": 1,
            "message": "",
            "data": data
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"status": 0, "message": str(e), "data": {}}
        )

@app.post("/register", tags=["Register"])
async def register(data: RegisterRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        existing_user = db.query(Users).filter(
            or_(Users.username == data.username, Users.email == data.email)
        ).first()

        if existing_user:
            raise HTTPException(
                status_code=400,
                detail={"status": 0, "message": "Username or email already exists", "data": {}}
            )

        hashed_password = pwd_context.hash(data.password)

        verification_token = str(uuid.uuid4())
        token_expiry = datetime.utcnow() + timedelta(minutes=10)

        new_user = Users(
            first_name=data.first_name,
            last_name=data.last_name,
            username=data.username,
            email=data.email,
            phone=data.phone,
            password=hashed_password
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        new_token = Token(
            user_id=new_user.user_id,
            verification_token=verification_token,
            token_expiry=token_expiry
        )

        db.add(new_token)
        db.commit()

        background_tasks.add_task(send_verification_email, data.email, verification_token)

        return {
            "status": 1,
            "message": "User registered successfully. Please verify your email.",
            "data": {
                "user_id": new_user.user_id,
                "username": new_user.username,
                "email": new_user.email
            }
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={"status": 0, "message": str(e), "data": {}}
        )
@app.post("/login", tags=["Login"])
async def login(req: LoginRequest = Body(...), db: Session = Depends(get_db)):
    try:
        user_data = db.query(Users).filter(
            or_(Users.email == req.username_or_email, Users.username == req.username_or_email)
        ).first()

        if not user_data:
            raise HTTPException(
                status_code=400,
                detail={"status": 0, "message": "User not found", "data": {}}
            )

        if not pwd_context.verify(req.password, user_data.password):
            raise HTTPException(
                status_code=400,
                detail={"status": 0, "message": "Invalid password", "data": {}}
            )

        return {
            "status": 1,
            "message": "Login successful",
            "data": {
                "user_id": user_data.user_id,
                "username": user_data.username,
                "email": user_data.email
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"status": 0, "message": str(e), "data": {}}
        )

@app.post("/add_node", tags=["Node"])
async def add_node(req: NodeRequest, db: Session = Depends(get_db)):
    try:
        new_node = Nodes(
            node_id=req.node_id,
            node_name=req.node_name,
            location=req.location,
            description=req.description,
            user_id=req.user_id
        )
        db.add(new_node)
        db.commit()
        return {
            "status": 1,
            "message": "Node added successfully",
            "data": {
                "node_id": new_node.node_id
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"status": 0, "message": str(e), "data": {}}
        )

@app.get("/verify-email")
async def verify_email(token: str, db: Session = Depends(get_db)):
    try:
        user = db.query(Users).filter(Users.verification_token == token).first()

        if not user:
            raise HTTPException(status_code=400, detail="Invalid or expired token")

        if user.is_token_expired():
            user.verification_token = None
            db.commit()
            raise HTTPException(status_code=400, detail="Token has expired")

        user.is_verified = True
        user.verification_token = None
        user.token_expiry = None
        db.commit()

        return {"message": "Email verified successfully. You can now log in."}
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"status": 0, "message": str(e), "data": {}}
        )

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("main:app", host="0.0.0.0", port=8086, reload=True)
