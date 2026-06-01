import logging
import json
import asyncio
import threading
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from config import BOT_TOKEN, ADMIN_ID, PORT, HOST, WEBHOOK_PATH
from database import init_database, add_user
from signals import process_signal
from tracking import handle_callback
from menu import cmd_start, cmd_capital, cmd_adduser, cmd_removeuser, cmd_listusers, cmd_status, cmd_report, cmd_weekly, handle_menu_callback
from reports import send_daily_report, send_weekly_report

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app_telegram = None

def build_app():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("capital", cmd_capital))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("weekly", cmd_weekly))
    app.add_handler(CommandHandler("adduser", cmd_adduser))
    app.add_handler(CommandHandler("removeuser", cmd_removeuser))
    app.add_handler(CommandHandler("listusers", cmd_listusers))
    app.add_handler(CallbackQueryHandler(handle_menu_callback, pattern="^(boton|status|report|my_capital|manage_users|settings)"))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^(tp|sl|be|reentry|confirm|cancel)"))
    return app

async def webhook_handler(request):
    try:
        data = json.loads(await request.text())
        result = await process_signal(data, app_telegram.bot)
        return web.json_response({"status": "ok"})
    except Exception as e:
        return web.json_response({"status": "error"}, status=500)

async def health(request):
    return web.json_response({"status": "ok"})

def run_server():
    async def start():
        wa = web.Application()
        wa.router.add_post(WEBHOOK_PATH, webhook_handler)
        wa.router.add_get("/", health)
        wa.router.add_get("/health", health)
        runner = web.AppRunner(wa)
        await runner.setup()
        await web.TCPSite(runner, HOST, PORT).start()
        logger.info(f"Webhook server started on port {PORT}")
        while True:
            await asyncio.sleep(3600)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start())

def main():
    global app_telegram
    init_database()
    add_user(ADMIN_ID, "Admin", "admin")
    app_telegram = build_app()
    threading.Thread(target=run_server, daemon=True).start()
    sched = AsyncIOScheduler(timezone="Europe/Paris")
    sched.add_job(send_daily_report, CronTrigger(hour=20, minute=0), args=[app_telegram.bot])
    sched.add_job(send_weekly_report, CronTrigger(day_of_week=6, hour=20), args=[app_telegram.bot])
    sched.start()
    logger.info("Bot RSV Trading started!")
    app_telegram.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
