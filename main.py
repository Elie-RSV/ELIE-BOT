"""
RSV Trading Bot — Point d'entrée principal
Bot Telegram Trading Signal avec webhook TradingView
"""
import logging
import json
import asyncio
from aiohttp import web
from telegram import Bot, Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import (
    BOT_TOKEN, ADMIN_ID, PORT, HOST, WEBHOOK_PATH,
    DAILY_REPORT_HOUR, DAILY_REPORT_MINUTE,
    WEEKLY_REPORT_DAY, WEEKLY_REPORT_HOUR
)
from database import init_database, add_user
from signals import process_signal
from tracking import handle_callback
from menu import (
    cmd_start, cmd_capital, cmd_adduser, cmd_removeuser,
    cmd_listusers, cmd_status, cmd_report, cmd_weekly,
    handle_menu_callback
)
from reports import send_daily_report, send_weekly_report

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================================
# APPLICATION TELEGRAM
# ============================================================
app_telegram: Application = None
scheduler: AsyncIOScheduler = None


def build_telegram_app() -> Application:
    """Construit et configure l'application Telegram"""
    application = Application.builder().token(BOT_TOKEN).build()

    # Commandes
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("capital", cmd_capital))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("report", cmd_report))
    application.add_handler(CommandHandler("weekly", cmd_weekly))
    application.add_handler(CommandHandler("adduser", cmd_adduser))
    application.add_handler(CommandHandler("removeuser", cmd_removeuser))
    application.add_handler(CommandHandler("listusers", cmd_listusers))

    # Callbacks boutons inline
    application.add_handler(CallbackQueryHandler(handle_menu_callback,
                             pattern="^(boton|status|report|my_capital|manage_users|settings)"))
    application.add_handler(CallbackQueryHandler(handle_callback,
                             pattern="^(tp|sl|be|reentry|confirm|cancel)"))

    return application


# ============================================================
# SERVEUR WEBHOOK (aiohttp)
# ============================================================

async def webhook_handler(request: web.Request) -> web.Response:
    """Reçoit les alertes TradingView via webhook"""
    try:
        body = await request.text()
        data = json.loads(body)
        logger.info(f"📡 Signal reçu: {data}")

        bot = app_telegram.bot
        result = await process_signal(data, bot)

        return web.json_response({"status": "ok", "result": result})

    except json.JSONDecodeError:
        logger.error("❌ JSON invalide reçu")
        return web.json_response({"status": "error", "message": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error(f"❌ Erreur webhook: {e}")
        return web.json_response({"status": "error", "message": str(e)}, status=500)


async def health_check(request: web.Request) -> web.Response:
    """Endpoint de santé pour Railway"""
    from signals import is_bot_active
    from database import get_today_session
    session = get_today_session()
    return web.json_response({
        "status": "healthy",
        "bot_active": is_bot_active(),
        "trades_today": session["trades_count"],
        "losses_today": session["losses_count"]
    })


async def telegram_update_handler(request: web.Request) -> web.Response:
    """Reçoit les updates Telegram via webhook"""
    try:
        body = await request.json()
        update = Update.de_json(body, app_telegram.bot)
        await app_telegram.process_update(update)
        return web.Response(status=200)
    except Exception as e:
        logger.error(f"❌ Erreur update Telegram: {e}")
        return web.Response(status=500)


def build_web_app() -> web.Application:
    """Construit le serveur web aiohttp"""
    web_app = web.Application()
    web_app.router.add_post(WEBHOOK_PATH, webhook_handler)
    web_app.router.add_post("/telegram", telegram_update_handler)
    web_app.router.add_get("/health", health_check)
    web_app.router.add_get("/", health_check)
    return web_app


# ============================================================
# SCHEDULER — Rapports automatiques
# ============================================================

def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Configure les tâches planifiées"""
    sched = AsyncIOScheduler(timezone="Europe/Paris")

    # Rapport quotidien à 20h
    sched.add_job(
        send_daily_report,
        CronTrigger(hour=DAILY_REPORT_HOUR, minute=DAILY_REPORT_MINUTE),
        args=[bot],
        id="daily_report",
        name="Rapport Quotidien"
    )

    # Rapport hebdomadaire le dimanche à 20h
    sched.add_job(
        send_weekly_report,
        CronTrigger(day_of_week=WEEKLY_REPORT_DAY, hour=WEEKLY_REPORT_HOUR),
        args=[bot],
        id="weekly_report",
        name="Rapport Hebdomadaire"
    )

    # Reset session à minuit
    sched.add_job(
        reset_daily_session,
        CronTrigger(hour=0, minute=1),
        args=[bot],
        id="reset_session",
        name="Reset Session"
    )

    return sched


async def reset_daily_session(bot: Bot):
    """Remet à zéro la session journalière à minuit"""
    from database import update_session
    from signals import set_bot_active
    update_session(is_active=True)
    logger.info("🔄 Session journalière réinitialisée")


# ============================================================
# DÉMARRAGE
# ============================================================

async def on_startup(web_app: web.Application):
    """Actions au démarrage du serveur"""
    global app_telegram, scheduler

    # Init DB
    init_database()

    # Enregistrement admin
    add_user(ADMIN_ID, "Admin", "admin")

    # Build Telegram app
    app_telegram = build_telegram_app()
    await app_telegram.initialize()
    await app_telegram.start()

    # Scheduler
    scheduler = setup_scheduler(app_telegram.bot)
    scheduler.start()

    # Notification démarrage
    try:
        await app_telegram.bot.send_message(
            chat_id=ADMIN_ID,
            text="🚀 *Bot RSV Trading démarré !*\n\nTape /start pour accéder au menu.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Erreur notification démarrage: {e}")

    logger.info(f"✅ Bot RSV Trading démarré sur le port {PORT}")


async def on_shutdown(web_app: web.Application):
    """Actions à l'arrêt du serveur"""
    global app_telegram, scheduler
    if scheduler:
        scheduler.shutdown()
    if app_telegram:
        await app_telegram.stop()
        await app_telegram.shutdown()
    logger.info("🛑 Bot RSV Trading arrêté")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    web_application = build_web_app()
    web_application.on_startup.append(on_startup)
    web_application.on_shutdown.append(on_shutdown)

    web.run_app(
        web_application,
        host=HOST,
        port=PORT
    )
