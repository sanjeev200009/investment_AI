# tasks/rules_tasks.py
"""
Autonomous Investment Rules Checker.

Runs on a schedule (every 15 min during market hours) and:
  1. Loads all active InvestmentRule rows.
  2. Fetches current MarketData for each affected symbol.
  3. Evaluates each rule's condition.
  4. If triggered, creates a Notification and dispatches FCM push.
  5. Uses the AI agent to generate a human-readable explanation of why
     the rule fired (so beginners understand what happened).

Supported condition_types:
  - price_above   : triggers when price > threshold
  - price_below   : triggers when price < threshold
  - change_pct_up : triggers when change_pct > threshold (e.g. +5%)
  - change_pct_down: triggers when change_pct < -threshold (e.g. -5%)
  - volume_spike  : triggers when volume > threshold
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from celery_worker import celery_app

logger = logging.getLogger(__name__)

CONDITION_EVALUATORS = {
    "price_above": lambda price, change_pct, volume, threshold: (
        price is not None and price > threshold
    ),
    "price_below": lambda price, change_pct, volume, threshold: (
        price is not None and price < threshold
    ),
    "change_pct_up": lambda price, change_pct, volume, threshold: (
        change_pct is not None and change_pct > threshold
    ),
    "change_pct_down": lambda price, change_pct, volume, threshold: (
        change_pct is not None and change_pct < -abs(threshold)
    ),
    "volume_spike": lambda price, change_pct, volume, threshold: (
        volume is not None and volume > threshold
    ),
}


@celery_app.task(bind=True, max_retries=3, name="tasks.rules_tasks.check_investment_rules")
def check_investment_rules(self):
    """
    Main scheduler task. Evaluates every active investment rule.
    Runs every 15 minutes via Celery Beat during market hours.
    """
    try:
        asyncio.run(_async_check_rules())
    except Exception as exc:
        logger.exception("check_investment_rules failed: %s", exc)
        raise self.retry(exc=exc, countdown=120)


async def _async_check_rules():
    from app.database import SessionLocal
    from app.models.portfolio import InvestmentRule
    from app.models.stock import MarketData
    from app.models.notification import Notification
    from app.models.user import User

    db = SessionLocal()
    try:
        rules = db.query(InvestmentRule).all()
        if not rules:
            logger.info("No investment rules found")
            return

        # Build symbol → latest MarketData map (one query per unique symbol)
        symbols = list({r.symbol for r in rules})
        market_map: dict[str, MarketData] = {}
        for sym in symbols:
            row = (
                db.query(MarketData)
                .filter(MarketData.symbol == sym)
                .order_by(MarketData.recorded_at.desc())
                .first()
            )
            if row:
                market_map[sym] = row

        triggered = 0
        for rule in rules:
            market = market_map.get(rule.symbol)
            if not market:
                continue

            evaluator = CONDITION_EVALUATORS.get(rule.condition_type)
            if not evaluator:
                logger.warning("Unknown condition_type: %s", rule.condition_type)
                continue

            fired = evaluator(
                market.price,
                market.change_pct,
                market.volume,
                rule.threshold,
            )
            if not fired:
                continue

            # Check if we already sent this notification recently (dedup window 1h)
            from datetime import timedelta
            from sqlalchemy import and_
            recent = (
                db.query(Notification)
                .filter(
                    and_(
                        Notification.user_id == rule.user_id,
                        Notification.type == "rule_alert",
                        Notification.message.like(f"%{rule.symbol}%"),
                        Notification.timestamp
                        >= datetime.now(timezone.utc) - timedelta(hours=1),
                    )
                )
                .first()
            )
            if recent:
                continue

            # Generate AI explanation
            explanation = await _generate_rule_explanation(rule, market)

            # Create DB notification
            notif = Notification(
                user_id=rule.user_id,
                type="rule_alert",
                message=explanation,
                is_read=False,
                timestamp=datetime.now(timezone.utc),
            )
            db.add(notif)
            db.commit()
            db.refresh(notif)

            # Dispatch FCM push
            _send_push_for_rule.delay(
                user_id=str(rule.user_id),
                symbol=rule.symbol,
                condition_type=rule.condition_type,
                threshold=rule.threshold,
                current_price=market.price,
                change_pct=market.change_pct,
                notification_id=notif.notif_id,
            )
            triggered += 1
            logger.info(
                "Rule fired: user=%s symbol=%s condition=%s",
                rule.user_id, rule.symbol, rule.condition_type,
            )

        logger.info(
            "Rule check complete: %d rules evaluated, %d triggered",
            len(rules), triggered,
        )
    finally:
        db.close()


async def _generate_rule_explanation(rule, market) -> str:
    """
    Use the AI agent to write a plain-language explanation of why the rule fired.
    Falls back to a template string if the LLM is unavailable.
    """
    condition_labels = {
        "price_above": f"risen above LKR {rule.threshold:,.2f}",
        "price_below": f"fallen below LKR {rule.threshold:,.2f}",
        "change_pct_up": f"gained more than {rule.threshold}% today",
        "change_pct_down": f"dropped more than {abs(rule.threshold)}% today",
        "volume_spike": f"hit a volume spike above {rule.threshold:,.0f} shares",
    }
    label = condition_labels.get(rule.condition_type, "met your alert condition")

    fallback = (
        f"Alert: {rule.symbol} has {label}. "
        f"Current price: LKR {market.price:,.2f} "
        f"({'+' if (market.change_pct or 0) >= 0 else ''}"
        f"{market.change_pct or 0:.2f}%). "
        f"Review your investment plan before making decisions."
    )

    try:
        import httpx
        from app.config import get_settings

        settings = get_settings()
        api_key = getattr(settings, "OPENROUTER_API_KEY", "")
        if not api_key:
            return fallback

        prompt = (
            f"Write a short (2-3 sentences), beginner-friendly alert message for an investor. "
            f"Their stock alert fired: {rule.symbol} has {label}. "
            f"Current price is LKR {market.price:,.2f} with a "
            f"{market.change_pct or 0:.2f}% change today. "
            f"End with one sentence of cautious, educational advice. "
            f"Do not use jargon. Do not recommend buying or selling."
        )
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "google/gemini-flash-1.5",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                    "temperature": 0.4,
                },
            )
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning("AI explanation failed (%s), using fallback", e)
        return fallback


@celery_app.task(bind=True, max_retries=3, name="tasks.rules_tasks.send_push_for_rule")
def _send_push_for_rule(
    self,
    user_id: str,
    symbol: str,
    condition_type: str,
    threshold: float,
    current_price: float,
    change_pct: float,
    notification_id: int,
):
    """Send an FCM push notification for a triggered investment rule."""
    try:
        asyncio.run(
            _async_send_push(
                user_id, symbol, condition_type,
                threshold, current_price, change_pct, notification_id,
            )
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


async def _async_send_push(
    user_id: str,
    symbol: str,
    condition_type: str,
    threshold: float,
    current_price: float,
    change_pct: float,
    notification_id: int,
):
    from app.database import SessionLocal
    from app.services.fcm import send_push_to_user

    db = SessionLocal()
    try:
        title = f"📊 {symbol} Alert Triggered"
        body = (
            f"{symbol} is now at LKR {current_price:,.2f} "
            f"({'+' if change_pct >= 0 else ''}{change_pct:.2f}%)"
        )
        await send_push_to_user(
            db=db,
            user_id=user_id,
            title=title,
            body=body,
            data={
                "type": "rule_alert",
                "symbol": symbol,
                "notification_id": str(notification_id),
                "current_price": str(current_price),
            },
        )
    finally:
        db.close()
