"""
Module Signaux — Réception webhook TradingView + génération fiches signal
"""
import json
import logging
from datetime import date
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from config import MAX_TRADES_PER_DAY, MAX_LOSSES_PER_DAY, MIN_RR_RATIO
from database import (
    get_today_session, update_session, save_trade,
    is_session_active, get_all_users
)
from money_management import (
    calculate_lot, calculate_pnl, calculate_rr,
    is_rr_valid, get_risk_label
)

logger = logging.getLogger(__name__)

# ============================================================
# ÉTAT DU BOT (ON/OFF)
# ============================================================
bot_state = {"active": False}


def set_bot_active(state: bool):
    bot_state["active"] = state


def is_bot_active() -> bool:
    return bot_state["active"]


# ============================================================
# TRAITEMENT DU SIGNAL TRADINGVIEW
# ============================================================

async def process_signal(data: dict, bot: Bot) -> dict:
    """
    Traite un signal reçu depuis TradingView
    Retourne le résultat du traitement
    """
    # Vérification bot actif
    if not is_bot_active():
        logger.info("Signal reçu mais bot inactif")
        return {"status": "ignored", "reason": "Bot inactif"}

    # Vérification session active
    if not is_session_active():
        logger.info("Session journalière stoppée")
        return {"status": "ignored", "reason": "Session stoppée"}

    # Récupération session
    session = get_today_session()

    # Vérification max trades
    if session["trades_count"] >= MAX_TRADES_PER_DAY:
        await notify_all(bot, "⚠️ *Limite atteinte* — 10 trades maximum pour aujourd'hui.")
        return {"status": "ignored", "reason": "Max trades atteint"}

    # Vérification max pertes
    if session["losses_count"] >= MAX_LOSSES_PER_DAY:
        return {"status": "ignored", "reason": "Session stoppée — 2 pertes"}

    # Extraction données
    pair = data.get("pair", "XAUUSD").upper()
    direction = data.get("direction", "BUY").upper()
    entry = float(data.get("entry", 0))
    tp = float(data.get("tp", 0))
    sl = float(data.get("sl", 0))
    timeframe = data.get("timeframe", "M5").upper()
    score = int(data.get("score", 3))

    # Validation données
    if entry == 0 or tp == 0 or sl == 0:
        return {"status": "error", "reason": "Données incomplètes"}

    # Vérification RR minimum 1:3
    rr = calculate_rr(entry, tp, sl)
    if not is_rr_valid(entry, tp, sl):
        logger.info(f"Signal ignoré — RR {rr} < {MIN_RR_RATIO}")
        return {"status": "ignored", "reason": f"RR insuffisant ({rr} < 1:{MIN_RR_RATIO})"}

    # Récupération tous les utilisateurs pour calcul MM admin
    from config import ADMIN_ID
    lot = calculate_lot(ADMIN_ID, entry, sl, pair)
    gain_est = calculate_pnl(lot, entry, tp, pair)
    risk_est = calculate_pnl(lot, entry, sl, pair)

    # Sauvegarde trade
    trade_data = {
        "date": date.today().isoformat(),
        "pair": pair,
        "direction": direction,
        "entry": entry,
        "tp": tp,
        "sl": sl,
        "lot": lot,
        "rr": rr,
        "score": score,
        "timeframe": timeframe
    }
    trade_id = save_trade(trade_data)

    # Mise à jour session
    update_session(trades_count=session["trades_count"] + 1)

    # Génération et envoi fiche signal
    await send_signal_to_all(bot, trade_id, trade_data, gain_est, risk_est, session["trades_count"] + 1)

    return {"status": "success", "trade_id": trade_id}


# ============================================================
# GÉNÉRATION FICHE SIGNAL
# ============================================================

def build_signal_message(trade_id: int, trade: dict, gain_est: float,
                          risk_est: float, trade_num: int) -> str:
    """Génère la fiche signal formatée"""
    direction_emoji = "📈" if trade["direction"] == "BUY" else "📉"
    score_stars = "⭐" * trade["score"] + "☆" * (5 - trade["score"])

    # Corrélation HTF/LTF — basée sur le score
    htf_ltf = "✅" if trade["score"] >= 3 else "⚠️"
    liquidity = "✅" if trade["score"] >= 2 else "⚠️"
    poi_zone = "✅" if trade["score"] >= 3 else "⚠️"
    crt_confirm = "✅" if trade["score"] >= 4 else "⚠️"

    msg = f"""
⚡ *SIGNAL RSV — TRADE #{trade_id}*
━━━━━━━━━━━━━━━━━━━━━
{direction_emoji} *Paire*      : `{trade['pair']}`
📍 *Position*   : *{trade['direction']}*
⏱️ *Timeframe*  : `{trade['timeframe']}`
━━━━━━━━━━━━━━━━━━━━━
🎯 *TP*         : `{trade['tp']}`
🛑 *SL*         : `{trade['sl']}`
🔑 *Entrée*     : `{trade['entry']}`
📦 *Lot*        : `{trade['lot']}`
━━━━━━━━━━━━━━━━━━━━━
💰 *Gain est.*  : `+{gain_est}$`
⚠️ *Risque*     : `-{abs(risk_est)}$`
📊 *RR*         : `1:{trade['rr']}`
━━━━━━━━━━━━━━━━━━━━━
{score_stars} *Score*     : `{trade['score']}/5`
━━━━━━━━━━━━━━━━━━━━━
🔗 *Corrélation HTF/LTF* : {htf_ltf}
💧 *Prise de liquidité*  : {liquidity}
📐 *Zone POI*            : {poi_zone}
🕯️ *CRT confirmé*        : {crt_confirm}
━━━━━━━━━━━━━━━━━━━━━
📊 *Trade {trade_num}/{10} aujourd'hui*
"""
    return msg.strip()


def build_signal_keyboard(trade_id: int) -> InlineKeyboardMarkup:
    """Boutons inline pour le suivi du trade"""
    keyboard = [
        [
            InlineKeyboardButton("✅ TP Touché", callback_data=f"tp_{trade_id}"),
            InlineKeyboardButton("❌ SL Touché", callback_data=f"sl_{trade_id}"),
        ],
        [
            InlineKeyboardButton("⚖️ Break Even", callback_data=f"be_{trade_id}"),
            InlineKeyboardButton("🔄 Re-entrée", callback_data=f"reentry_{trade_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# ============================================================
# ENVOI AUX UTILISATEURS
# ============================================================

async def send_signal_to_all(bot: Bot, trade_id: int, trade: dict,
                              gain_est: float, risk_est: float, trade_num: int):
    """Envoie la fiche signal à tous les utilisateurs autorisés"""
    message = build_signal_message(trade_id, trade, gain_est, risk_est, trade_num)
    keyboard = build_signal_keyboard(trade_id)
    users = get_all_users()

    from config import ADMIN_ID
    sent_ids = set()

    # Envoi admin
    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=message,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        sent_ids.add(ADMIN_ID)
    except Exception as e:
        logger.error(f"Erreur envoi admin: {e}")

    # Envoi abonnés
    for user in users:
        uid = user["user_id"]
        if uid not in sent_ids:
            try:
                await bot.send_message(
                    chat_id=uid,
                    text=message,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Erreur envoi user {uid}: {e}")


async def notify_all(bot: Bot, message: str):
    """Envoie une notification à tous les utilisateurs"""
    users = get_all_users()
    from config import ADMIN_ID

    sent_ids = set()
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=message, parse_mode="Markdown")
        sent_ids.add(ADMIN_ID)
    except Exception as e:
        logger.error(f"Erreur notif admin: {e}")

    for user in users:
        uid = user["user_id"]
        if uid not in sent_ids:
            try:
                await bot.send_message(chat_id=uid, text=message, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Erreur notif user {uid}: {e}")
