"""Beginner lessons (proposal 6.5 / FR-5). Content lives in app/content/lessons.py
so the Learn tab and the assistant's knowledge search read the same text."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.content.lessons import LESSONS, LESSONS_BY_ID
from app.dependencies import get_current_user, get_db
from app.models.evaluation import LessonView
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/learn', tags=['Learn'])


@router.get('/lessons')
def list_lessons(_: User = Depends(get_current_user)):
    return [
        {k: lesson[k] for k in ('id', 'title', 'theme', 'minutes', 'summary')}
        for lesson in LESSONS
    ]


@router.get('/lessons/{lesson_id}')
def get_lesson(lesson_id: str, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    lesson = LESSONS_BY_ID.get(lesson_id)
    if lesson is None:
        raise HTTPException(404, 'Lesson not found')
    # Evaluation plan E7 (lessons opened). Best effort: a failed write must
    # never stop the lesson from showing.
    try:
        db.add(LessonView(user_id=user.user_id, lesson_id=lesson_id))
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning('Could not record lesson view: %s', exc)
    return {
        **{k: lesson[k] for k in ('id', 'title', 'theme', 'minutes', 'summary', 'key_terms')},
        'sections': [{'heading': h, 'body': b} for h, b in lesson['sections']],
    }
