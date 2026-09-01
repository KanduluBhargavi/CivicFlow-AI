from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from fastapi import UploadFile, File, Form
from datetime import datetime, timezone
import os
import shutil
import uuid
import pandas as pd

from app.utils.auth import get_current_user
from app.models.user import User
from app.database import SessionLocal
from app.models.complaint import Complaint

from app.services.notification_service import send_email

from app.services.ai_service import (
    detect_language,
    translate_text,
    predict_department,
    predict_priority,
    summarize_complaint,
    get_department_id
)
UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

router=APIRouter()

def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()

coordinates_df = pd.read_csv(
    r"C:\Users\kandu\OneDrive\Desktop\CivicFlow-AI\dataset\district_coordinates.csv"
)

def get_coordinates(state: str, district: str):

    state = state.strip().lower()
    district = district.strip().lower()

    # Clean the CSV values too
    coordinates_df["state_clean"] = (
        coordinates_df["state"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    coordinates_df["district_clean"] = (
        coordinates_df["district"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    match = coordinates_df[
        (coordinates_df["state_clean"] == state) &
        (coordinates_df["district_clean"] == district)
    ]

    if match.empty:
        print(f"Coordinates not found for: '{district}', '{state}'")
        print("Available matching state districts:")
        print(
            coordinates_df[
                coordinates_df["state_clean"] == state
            ][["state", "district"]]
        )

        return 0.0, 0.0

    latitude = float(match.iloc[0]["latitude"])
    longitude = float(match.iloc[0]["longitude"])

    print(f"Coordinates found: {district}, {state} -> {latitude}, {longitude}")

    return latitude, longitude



@router.post("/complaints")
def create_complaint(

    background_tasks: BackgroundTasks,

    title: str = Form(...),

    description: str = Form(...),

    state: str = Form(...),

    district: str = Form(...),

    area: str = Form(...),

    address: str = Form(...),

    landmark: str = Form(""),

    pincode: str = Form(...),

    file: UploadFile = File(None),

    current_user: User = Depends(get_current_user),

    db: Session = Depends(get_db)

):

    try:

        # =========================
        # CLEAN LOCATION DATA
        # =========================

        state = " ".join(state.strip().split()).title()

        district = " ".join(
            district.strip().split()
        ).title()


        # =========================
        # AI PROCESSING
        # =========================

        language = detect_language(description)

        translated_text = translate_text(description)

        predicted_department = predict_department(
            translated_text
        )

        department_id = get_department_id(
            predicted_department
        )

        priority = predict_priority(
            translated_text
        )

        summary = summarize_complaint(
            translated_text
        )


        # =========================
        # LOCATION COORDINATES
        # =========================

        latitude, longitude = get_coordinates(
            state,
            district
        )


        # =========================
        # FILE UPLOAD
        # =========================

        media_path = None

        if file and file.filename:

            allowed_extensions = [

                ".jpg",
                ".jpeg",
                ".png",
                ".mp4",
                ".mov",
                ".avi"

            ]

            extension = os.path.splitext(
                file.filename
            )[1].lower()


            if extension not in allowed_extensions:

                raise HTTPException(

                    status_code=400,

                    detail="Only image and video files are allowed."

                )


            unique_filename = (

                f"{uuid.uuid4()}{extension}"

            )


            media_path = os.path.join(

                UPLOAD_FOLDER,

                unique_filename

            )


            with open(

                media_path,

                "wb"

            ) as buffer:

                shutil.copyfileobj(

                    file.file,

                    buffer

                )


        # =========================
        # CREATE COMPLAINT
        # =========================

        new_complaint = Complaint(

            citizen_id=current_user.user_id,

            department_id=department_id,

            title=title,

            description=description,

            state=state,

            district=district,

            area=area,

            address=address,

            landmark=landmark,

            pincode=pincode,

            latitude=latitude,

            longitude=longitude,

            language=language,

            translated_text=translated_text,

            predicted_department=predicted_department,

            priority=priority,

            ai_summary=summary,

            media_path=media_path,

            status="Assigned",

            assigned_at=datetime.now(timezone.utc)

        )


        db.add(new_complaint)

        db.commit()

        db.refresh(new_complaint)


        # =========================
        # SEND CONFIRMATION EMAIL
        # =========================

        email_message = f"""

        <div style="
            font-family: Arial, sans-serif;
            padding: 20px;
        ">

            <h2 style="color:#2563eb;">
                Complaint Successfully Submitted ✅
            </h2>

            <p>
                Hello <strong>{current_user.full_name}</strong>,
            </p>

            <p>
                Thank you for submitting your complaint through
                <strong>CivicFlow AI</strong>.
            </p>

            <p>
                Your complaint has been successfully registered
                and routed to the appropriate department.
            </p>

            <hr>

            <p>
                <strong>Complaint ID:</strong>
                #{new_complaint.complaint_id}
            </p>

            <p>
                <strong>Complaint Title:</strong>
                {new_complaint.title}
            </p>

            <p>
                <strong>Assigned Department:</strong>
                {predicted_department}
            </p>

            <p>
                <strong>Priority:</strong>
                {priority}
            </p>

            <hr>

            <p>
                📢 We will notify you whenever your complaint
                status changes.
            </p>

            <p>
                You can also log in to CivicFlow AI anytime
                to track your complaint.
            </p>

            <br>

            <p>
                Regards,<br>
                <strong>CivicFlow AI Support Team</strong>
            </p>

        </div>

        """


        background_tasks.add_task(

            send_email,

            current_user.email,

            "CivicFlow AI - Complaint Successfully Submitted",

            email_message

        )


        return {

            "message":
            "Complaint submitted successfully",

            "complaint_id":
            new_complaint.complaint_id,

            "department":
            predicted_department,

            "priority":
            priority

        }


    except HTTPException:

        raise


    except Exception as e:

        print("Complaint creation error:", str(e))

        raise HTTPException(

            status_code=500,

            detail="Unable to submit complaint."

        )

@router.get("/my-complaints")
def my_complaints(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    

    complaints = (
        db.query(Complaint)
        .filter(Complaint.citizen_id == current_user.user_id)
        .order_by(Complaint.created_at.desc())
        .all()
    )

    data = []

    for c in complaints:

        
        data.append({
            "complaint_id": c.complaint_id,
            "title": c.title,
            "department": c.predicted_department,
            "status": c.status,
            "priority": c.priority,
            "created_at": c.created_at,
            "summary": c.ai_summary
        })

    return data

@router.get("/complaints/{complaint_id}")
def complaint_details(
    complaint_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    complaint = (
        db.query(Complaint)
        .filter(
            Complaint.complaint_id == complaint_id,
            Complaint.citizen_id == current_user.user_id
        )
        .first()
    )

    if not complaint:
        return {"message": "Complaint not found"}

    return {
    "complaint_id": complaint.complaint_id,
    "title": complaint.title,
    "description": complaint.description,

    # AI Analysis
    "language": complaint.language,
    "translated_text": complaint.translated_text,
    "department": complaint.predicted_department,
    "priority": complaint.priority,
    "summary": complaint.ai_summary,

    # Complaint Information
    "state": complaint.state,
    "district": complaint.district,
    "area": complaint.area,

    # Status
    "status": complaint.status,

    # Dates
    "created_at": complaint.created_at,
    "assigned_at": complaint.assigned_at,
    "in_progress_at": complaint.in_progress_at,
    "resolved_at": complaint.resolved_at
}