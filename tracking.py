"""
Module Tracking — Suivi live des trades (TP / SL / BE / Re-entrée)
Gestion des callbacks des boutons inline
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import (
    get_trade, update_trade_status, get_today_session,
    update_session, is_session_active
)
from money_management import calculate_pnl
from signals import notify_all, set_bot_active, is_bot_active
from config import MAX_LOSSES_PER_DAY, ADMIN_ID

logger = logging.getLogger(__name__)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestionnaire principal des callbacks boutons inline"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    # Parsing callback
    parts = data.split("_")
    action = parts[0]
    trade_id = int(parts[1]) if len(parts) > 1 else None

    if action == "tp" and trade_id:
        await handle_tp(query, context, trade_id)
    elif action == "sl" and trade_id:
        await handle_sl(query, context, trade_id, user_id)
    elif action == "be" and trade_id:
        await handle_be(query, context, trade_id)
    elif action == "reentry" and trade_id:
        await handle_reentry(query, context, trade_id)
    elif action == "boton":
        await handle_bot_toggle(query, context)
    elif action == "status":
        await handle_status_check(query, context)
    elif action == "confirm":
        sub_action = parts[1] if len(parts) > 1 else ""
        trade_id = int(parts[2]) if len(parts) > 2 else None
        if sub_action == "tp":
            await confirm_tp(query, context, trade_id)
        elif sub_action == "sl":
            await confirm_sl(query, context, trade_id)


# ============================================================
# TP TOUCHÉ
# ============================================================

async def handle_tp(query, context, trade_id: int):
    """Demande confirmation avant de valider le TP"""
    trade = get_trade(trade_id)
    if not trade or trade["status"] != "open":
        await query.edit_message_text("⚠️ Ce trade est déjà clôturé.")
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirmer TP", callback_data=f"confirm_tp_{trade_id}"),
            InlineKeyboardButton("❌ Annuler", callback_data=f"cancel_{trade_id}")
        ]
    ])
    await query.edit_message_reply_markup(reply_markup=keyboard)
    await query.message.reply_text(
        f"🎯 Confirmer que le *TP est touché* pour le Trade #{trade_id} ?",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


async def confirm_tp(query, context, trade_id: int):
    """Valide le TP et notifie tous les utilisateurs"""
    trade = get_trade(trade_id)
    if not trade:
        return

    pnl = calculate_pnl(trade["lot"], trade["entry"], trade["tp"], trade["pair"])
    update_trade_status(trade_id, "win", pnl)
    update_session(wins_count=get_today_session()["wins_count"] + 1, total_pnl=pnl)

    msg = f"""
🎯 *TP TOUCHÉ — Trade #{trade_id}*
━━━━━━━━━━━━━━━━━━━━━
📈 *Paire*    : `{trade['pair']}`
📍 *Position* : *{trade['direction']}*
✅ *Résultat* : *WIN*
💰 *Gain*     : `+{pnl}$`
━━━━━━━━━━━━━━━━━━━━━
🏆 Excellent trade ! Discipline maintenue.
"""
    await notify_all(context.bot, msg)
    await query.edit_message_reply_markup(reply_markup=None)


# ============================================================
# SL TOUCHÉ
# ============================================================

async def handle_sl(query, context, trade_id: int, user_id: int):
    """Demande confirmation avant de valider le SL"""
    trade = get_trade(trade_id)
    if not trade or trade["status"] != "open":
        await query.edit_message_text("⚠️ Ce trade est déjà clôturé.")
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirmer SL", callback_data=f"confirm_sl_{trade_id}"),
            InlineKeyboardButton("❌ Annuler", callback_data=f"cancel_{trade_id}")
        ]
    ])
    await query.message.reply_text(
        f"🛑 Confirmer que le *SL est touché* pour le Trade #{trade_id} ?",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


async def confirm_sl(query, context, trade_id: int):
    """Valide le SL, vérifie la règle des 2 pertes"""
    trade = get_trade(trade_id)
    if not trade:
        return

    pnl = -calculate_pnl(trade["lot"], trade["entry"], trade["sl"], trade["pair"])
    update_trade_status(trade_id, "loss", pnl)

    session = get_today_session()
    new_losses = session["losses_count"] + 1
    update_session(losses_count=new_losses, total_pnl=pnl)

    msg = f"""
🛑 *SL TOUCHÉ — Trade #{trade_id}*
━━━━━━━━━━━━━━━━━━━━━
📈 *Paire*    : `{trade['pair']}`
📍 *Position* : *{trade['direction']}*
❌ *Résultat* : *LOSS*
💸 *Perte*    : `{pnl}$`
━━━━━━━━━━━━━━━━━━━━━
⚠️ *Pertes du jour* : {new_losses}/{MAX_LOSSES_PER_DAY}
"""

    # Vérification règle 2 SL
    if new_losses >= MAX_LOSSES_PER_DAY:
        update_session(is_active=False)
        set_bot_active(False)
        msg += f"""
━━━━━━━━━━━━━━━━━━━━━
🚨 *JOURNÉE STOPPÉE*
2 pertes atteintes — Aucun nouveau signal aujourd'hui.
Repos et analyse. On revient demain 💪
"""

    await notify_all(context.bot, msg)
    await query.edit_message_reply_markup(reply_markup=None)


# ============================================================
# BREAK EVEN
# ============================================================

async def handle_be(query, context, trade_id: int):
    """Notifie le passage au Break Even"""
    trade = get_trade(trade_id)
    if not trade or trade["status"] != "open":
        return

    update_trade_status(trade_id, "be", 0)

    msg = f"""
⚖️ *BREAK EVEN — Trade #{trade_id}*
━━━━━━━━━━━━━━━━━━━━━
📈 *Paire*    : `{trade['pair']}`
📍 *Position* : *{trade['direction']}*
⚖️ *Statut*   : *Break Even activé*
━━━━━━━━━━━━━━━━━━━━━
✅ SL déplacé à l'entrée — Trade sécurisé
📌 Si retour en zone de recharge → re-entrée possible
"""
    await notify_all(context.bot, msg)

    # Mise à jour boutons
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ TP Touché", callback_data=f"tp_{trade_id}"),
         InlineKeyboardButton("🔄 Re-entrée", callback_data=f"reentry_{trade_id}")]
    ])
    await query.edit_message_reply_markup(reply_markup=keyboard)


# ============================================================
# RE-ENTRÉE
# ============================================================

async def handle_reentry(query, context, trade_id: int):
    """Notifie une re-entrée après BE"""
    trade = get_trade(trade_id)
    if not trade:
        return

    msg = f"""
🔄 *RE-ENTRÉE — Trade #{trade_id}*
━━━━━━━━━━━━━━━━━━━━━
📈 *Paire*    : `{trade['pair']}`
📍 *Position* : *{trade['direction']}*
🔄 *Action*   : *Re-entrée en zone de recharge*
━━━━━━━━━━━━━━━━━━━━━
📌 Retour dans la zone POI confirmé
⚡ Attendre CRT de confirmation avant d'entrer
"""
    await notify_all(context.bot, msg)


# ============================================================
# TOGGLE BOT (ON/OFF)
# ============================================================

async def handle_bot_toggle(query, context):
    """Gère le bouton ON/OFF du bot"""
    current = is_bot_active()
    new_state = not current
    set_bot_active(new_state)

    if new_state:
        status_msg = "✅ *Bot ACTIVÉ*\nSurveillance des signaux en cours..."
        emoji = "🟢"
    else:
        status_msg = "🔴 *Bot DÉSACTIVÉ*\nPlus aucun signal ne sera envoyé."
        emoji = "🔴"

    await query.answer(f"{emoji} Bot {'activé' if new_state else 'désactivé'}")

    # Mise à jour du menu
    from menu import build_main_keyboard
    keyboard = build_main_keyboard()
    await query.edit_message_reply_markup(reply_markup=keyboard)
    await query.message.reply_text(status_msg, parse_mode="Markdown")


async def handle_status_check(query, context):
    """Vérifie le statut du système"""
    session = get_today_session()
    active = is_bot_active()

    status = "🟢 *ACTIF*" if active else "🔴 *INACTIF*"
    session_ok = "✅ Ouverte" if session["is_active"] else "🚨 Stoppée"

    msg = f"""
📡 *STATUT DU SYSTÈME*
━━━━━━━━━━━━━━━━━━━━━
🤖 *Bot*          : {status}
📅 *Session*       : {session_ok}
━━━━━━━━━━━━━━━━━━━━━
📊 *Trades*        : {session['trades_count']}/10
✅ *Wins*          : {session['wins_count']}
❌ *Losses*        : {session['losses_count']}/2
💰 *PnL du jour*   : {'+' if session['total_pnl'] >= 0 else ''}{round(session['total_pnl'], 2)}$
━━━━━━━━━━━━━━━━━━━━━
{'✅ Tout fonctionne normalement' if active and session['is_active'] else '⚠️ Vérifier les paramètres'}
"""
    await query.message.reply_text(msg, parse_mode="Markdown")
