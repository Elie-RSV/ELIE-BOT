import logging  
import json  
import asyncio  
import threading  
from aiohttp import web  
from telegram import Bot, Update  
from telegram.ext import Application, CommandHandler, CallbackQueryHandler  
from apscheduler.schedulers.asyncio import AsyncIOScheduler  
from apscheduler.triggers.cron import CronTrigger  
from config import BOT_TOKEN, ADMIN_ID, PORT, HOST, WEBHOOK_PATH, DAILY_REPORT_HOUR, DAILY_REPORT_MINUTE, WEEKLY_REPORT_DAY, WEEKLY_REPORT_HOUR  
from database import init_database, add_user  
from signals import process_signal  
from tracking import handle_callback  
from menu import cmd_start, cmd_capital, cmd_adduser, cmd_removeuser, cmd_listusers, cmd_status, cmd_report, cmd_weekly, handle_menu_callback  
from reports import send_daily_report, send_weekly_report

logging.basicConfig(format="%(asctime)s — %(name)s — %(levelname)s — %(message)s", level=logging.INFO)  
logger = logging.getLogger(__name__)  
app_telegram = None

def build_telegram_app():  
    application = Application.builder().token(BOT_TOKEN).build()  
    application.add_handler(CommandHandler("start", cmd_start))  
    application.add_handler(CommandHandler("capital", cmd_capital))  
    application.add_handler(CommandHandler("status", cmd_status))  
    application.add_handler(CommandHandler("report", cmd_report))  
    application.add_handler(CommandHandler("weekly", cmd_weekly))  
    application.add_handler(CommandHandler("adduser", cmd_adduser))  
    application.add_handler(CommandHandler("removeuser", cmd_removeuser))  
    application.add_handler(CommandHandler("listusers", cmd_listusers))  
    application.add_handler(CallbackQueryHandler(handle_menu_callback, pattern="^(boton|status|report|my_capital|manage_users|settings)"))  
    application.add_handler(CallbackQueryHandler(handle_callback, pattern="^(tp|sl|be|reentry|confirm|cancel)"))  
    return application

async def webhook_handler(request):  
    try:  
        data = json.loads(await request.text())  
        result = await process_signal(data, app_telegram.bot)  
        return web.json_response({"status": "ok", "result": result})  
    except Exception as e:  
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def health_check(request):  
    return web.json_response({"status": "healthy"})

def run_webhook_server():  
    async def start():  
        web_app = web.Application()  
        web_app.router.add_post(WEBHOOK_PATH, webhook_handler)  
        web_app.router.add_get("/health", health_check)  
        web_app.router.add_get("/", health_check)  
        runner = web.AppRunner(web_app)  
        await runner.setup()  
        await web.TCPSite(runner, HOST, PORT).start()  
        logger.info(f"✅ Webhook server started on port {PORT}")  
        while True:  
            await asyncio.sleep(3600)  
    loop = asyncio.new_event_loop()  
    asyncio.set_event_loop(loop)  
    loop.run_until_complete(start())

async def reset_daily_session(bot):  
    from database import update_session  
    update_session(is_active=True)

def main():  
    global app_telegram  
    init_database()  
    add_user(ADMIN_ID, "Admin", "admin")  
    app_telegram = build_telegram_app()  
    threading.Thread(target=run_webhook_server, daemon=True).start()  
    sched = AsyncIOScheduler(timezone="Europe/Paris")  
    sched.add_job(send_daily_report, CronTrigger(hour=DAILY_REPORT_HOUR, minute=DAILY_REPORT_MINUTE), args=[app_telegram.bot])  
    sched.add_job(send_weekly_report, CronTrigger(day_of_week=WEEKLY_REPORT_DAY, hour=WEEKLY_REPORT_HOUR), args=[app_telegram.bot])  
    sched.add_job(reset_daily_session, CronTrigger(hour=0, minute=1), args=[app_telegram.bot])  
    sched.start()  
    logger.info("🚀 Bot RSV Trading started in polling mode!")  
    app_telegram.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":  
    main()  
