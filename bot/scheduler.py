from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta, timezone
from .handlers import check_trophy
from .database import reset_player_stats

UTC_MINUS_5 = timezone(timedelta(hours=-5))

def setup_scheduler(application):
    scheduler = AsyncIOScheduler(timezone=UTC_MINUS_5)
    scheduler.add_job(check_trophy, 'interval', seconds=45, args=[application])
    scheduler.add_job(reset_player_stats, 'cron', hour=0, minute=0, args=[application])
    scheduler.start()
