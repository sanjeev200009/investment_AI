from fastapi import APIRouter, Depends
from typing import List

router = APIRouter()

@router.get("/")
def get_notifications():
    """
    Get all unread notifications for the user.
    """
    return []

@router.post("/{notification_id}/read")
def mark_as_read(notification_id: int):
    """
    Mark a notification as read.
    """
    return {"status": "success"}
