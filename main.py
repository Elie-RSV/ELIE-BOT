"""
RSV Trading Bot — Point d'entrée principal
Mode : Polling Telegram + Webhook TradingView (aiohttp)
"""
import logging
import json
import asyncio
import threading
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
# SERVEUR WEBHOOK TRADINGVIEW (aiohttp)
# ============================================================

app_telegram: Application = None

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


def run_webhook_server():
    """Lance le serveur webhook dans un thread séparé"""
    async def start_server():
        web_app = web.Application()
        web_app.router.add_post(WEBHOOK_PATH, webhook_handler)
        web_app.router.add_get("/health", health_check)
        web_app.router.add_get("/", health_check)

        runner = web.AppRunner(web_app)
        await runner.setup()
        site = web.TCPSite(runner, HOST, PORT)
        await site.start()
        logger.info(f"✅ Serveur webhook démarré sur le port {PORT}")

        # Garder le serveur en vie
        while True:
            await asyncio.sleep(3600)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_server())


# ============================================================
# SCHEDULER
# ============================================================

def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Configure les tâches planifiées"""
    sched = AsyncIOScheduler(timezone="Europe/Paris")

    sched.add_job(
        send_daily_report,
        CronTrigger(hour=DAILY_REPORT_HOUR, minute=DAILY_REPORT_MINUTE),
        args=[bot],
        id="daily_report",
        name="Rapport Quotidien"
    )

    sched.add_job(
        send_weekly_report,
        CronTrigger(day_of_week=WEEKLY_REPORT_DAY, hour=WEEKLY_REPORT_HOUR),
        args=[bot],
        id="weekly_report",
        name="Rapport Hebdomadaire"
    )

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
    update_session(is_active=True)
    logger.info("🔄 Session journalière réinitialisée")


# ============================================================
# MAIN
# ============================================================

def main():
    global app_telegram

    # Init DB
    init_database()

    # Enregistrement admin
    add_user(ADMIN_ID, "Admin", "admin")

    # Build Telegram app
    app_telegram = build_telegram_app()

    # Lancer le serveur webhook dans un thread séparé
    webhook_thread = threading.Thread(target=run_webhook_server, daemon=True)
    webhook_thread.start()
    logger.info("✅ Serveur webhook lancé en arrière-plan")

    # Scheduler
    scheduler = setup_scheduler(app_telegram.bot)
    scheduler.start()

    logger.info("🚀 Bot RSV Trading démarré en mode polling !")

    # Lancer le bot en mode polling
    app_telegram.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
