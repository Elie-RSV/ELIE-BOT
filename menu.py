"""
Module Menu — Interface principale du bot
Menu ON/OFF, commandes admin, gestion utilisateurs
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from security import admin_only, authorized_only, is_admin
from signals import is_bot_active, set_bot_active
from database import (
    add_user, remove_user, get_all_users, get_user,
    set_user_capital, get_user_capital, get_today_session,
    is_session_active, update_session
)
from money_management import get_mm_summary
from reports import generate_daily_report, generate_weekly_report
from config import ADMIN_ID

logger = logging.getLogger(__name__)


# ============================================================
# CLAVIER PRINCIPAL
# ============================================================

def build_main_keyboard(is_admin_user: bool = False) -> InlineKeyboardMarkup:
    """Construit le menu principal selon le rôle"""
    active = is_bot_active()
    session_ok = is_session_active()

    toggle_text = "🔴 Désactiver le Bot" if active else "🟢 Activer le Bot"
    status_text = "🟢 Bot Actif" if active else "🔴 Bot Inactif"

    keyboard = [
        # Bouton ON/OFF principal
        [InlineKeyboardButton(toggle_text, callback_data="boton_toggle")],
        # Statut
        [InlineKeyboardButton("📡 Vérifier le Statut", callback_data="status_check")],
        # Rapports
        [
            InlineKeyboardButton("📊 Rapport du Jour", callback_data="report_daily"),
            InlineKeyboardButton("📅 Rapport Hebdo", callback_data="report_weekly"),
        ],
        # Mon compte
        [InlineKeyboardButton("💰 Mon Capital & MM", callback_data="my_capital")],
    ]

    # Options admin uniquement
    if is_admin_user:
        keyboard.append([
            InlineKeyboardButton("👥 Gérer Abonnés", callback_data="manage_users"),
            InlineKeyboardButton("⚙️ Paramètres", callback_data="settings"),
        ])

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# COMMANDE /start
# ============================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande de démarrage — affiche le menu principal"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Utilisateur"
    admin = is_admin(user_id)

    if not admin and not get_user(user_id):
        await update.message.reply_text(
            "⛔ *Accès non autorisé.*\nContacte l'administrateur pour obtenir l'accès.",
            parse_mode="Markdown"
        )
        return

    active = is_bot_active()
    session = get_today_session()
    status_emoji = "🟢" if active else "🔴"
    role_label = "👑 Admin" if admin else "👤 Abonné"

    welcome = f"""
🤖 *BOT RSV TRADING*
━━━━━━━━━━━━━━━━━━━━━
👋 Bienvenue, *{username}*
🎭 Rôle : {role_label}
━━━━━━━━━━━━━━━━━━━━━
{status_emoji} *Statut Bot* : {'Actif' if active else 'Inactif'}
📊 *Trades aujourd'hui* : {session['trades_count']}/10
✅ *Wins* : {session['wins_count']} | ❌ *Losses* : {session['losses_count']}/2
━━━━━━━━━━━━━━━━━━━━━
Utilise le menu ci-dessous pour tout contrôler 👇
"""

    keyboard = build_main_keyboard(is_admin_user=admin)
    await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=keyboard)


# ============================================================
# GESTION CAPITAL
# ============================================================

async def cmd_capital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /capital [montant] — définir son capital"""
    user_id = update.effective_user.id

    if not is_admin(user_id) and not get_user(user_id):
        return

    if not context.args:
        capital = get_user_capital(user_id)
        mm = get_mm_summary(user_id)
        msg = f"""
💰 *TON CAPITAL & MONEY MANAGEMENT*
━━━━━━━━━━━━━━━━━━━━━
💵 *Capital*      : `{capital}$`
📈 *Profit cumulé*: `{mm['profit_pct']}%`
━━━━━━━━━━━━━━━━━━━━━
{mm['level_label']}
💸 *Risque/trade* : `{mm['risk_pct']}%` = `{mm['risk_amount']}$`
━━━━━━━━━━━━━━━━━━━━━
Pour modifier : `/capital [montant]`
Exemple : `/capital 5000`
"""
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    try:
        amount = float(context.args[0])
        if amount <= 0:
            raise ValueError
        set_user_capital(user_id, amount)
        mm = get_mm_summary(user_id)
        msg = f"""
✅ *Capital mis à jour !*
━━━━━━━━━━━━━━━━━━━━━
💵 *Nouveau capital* : `{amount}$`
━━━━━━━━━━━━━━━━━━━━━
{mm['level_label']}
💸 *Risque/trade*    : `{mm['risk_pct']}%` = `{mm['risk_amount']}$`
"""
        await update.message.reply_text(msg, parse_mode="Markdown")
    except (ValueError, IndexError):
        await update.message.reply_text(
            "❌ Format invalide.\nUtilise : `/capital 5000`",
            parse_mode="Markdown"
        )


# ============================================================
# GESTION ABONNÉS (ADMIN)
# ============================================================

@admin_only
async def cmd_adduser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /adduser [user_id] [username] — ajouter un abonné"""
    if len(context.args) < 1:
        await update.message.reply_text(
            "❌ Usage : `/adduser [user_id] [username]`\nExemple : `/adduser 123456789 john`",
            parse_mode="Markdown"
        )
        return

    try:
        new_user_id = int(context.args[0])
        username = context.args[1] if len(context.args) > 1 else "Abonné"
        add_user(new_user_id, username, "subscriber")
        await update.message.reply_text(
            f"✅ *Abonné ajouté !*\n👤 `{username}` (ID: `{new_user_id}`)",
            parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("❌ ID invalide. L'ID doit être un nombre.")


@admin_only
async def cmd_removeuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /removeuser [user_id] — supprimer un abonné"""
    if not context.args:
        await update.message.reply_text(
            "❌ Usage : `/removeuser [user_id]`",
            parse_mode="Markdown"
        )
        return

    try:
        target_id = int(context.args[0])
        remove_user(target_id)
        await update.message.reply_text(
            f"✅ *Abonné supprimé* (ID: `{target_id}`)",
            parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("❌ ID invalide.")


@admin_only
async def cmd_listusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /listusers — voir tous les abonnés"""
    users = get_all_users()
    if not users:
        await update.message.reply_text("📭 Aucun abonné pour l'instant.")
        return

    msg = "👥 *LISTE DES ABONNÉS*\n━━━━━━━━━━━━━━━━━━━━━\n"
    for i, user in enumerate(users, 1):
        role_emoji = "👑" if user["role"] == "admin" else "👤"
        msg += f"{i}. {role_emoji} `{user['username']}` — ID: `{user['user_id']}`\n"

    msg += f"━━━━━━━━━━━━━━━━━━━━━\n📊 Total : *{len(users)} abonné(s)*"
    await update.message.reply_text(msg, parse_mode="Markdown")


# ============================================================
# COMMANDES RAPIDES
# ============================================================

@authorized_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /status — statut rapide"""
    session = get_today_session()
    active = is_bot_active()
    status = "🟢 *ACTIF*" if active else "🔴 *INACTIF*"

    msg = f"""
📡 *STATUT RAPIDE*
━━━━━━━━━━━━━━━━━━━━━
🤖 Bot          : {status}
📅 Session      : {'✅ Ouverte' if session['is_active'] else '🚨 Stoppée'}
━━━━━━━━━━━━━━━━━━━━━
📊 Trades       : {session['trades_count']}/10
✅ Wins         : {session['wins_count']}
❌ Losses       : {session['losses_count']}/2
💰 PnL          : {'+' if session['total_pnl'] >= 0 else ''}{round(session['total_pnl'], 2)}$
━━━━━━━━━━━━━━━━━━━━━
{'✅ Tout fonctionne' if active and session['is_active'] else '⚠️ Vérifier les paramètres'}
"""
    await update.message.reply_text(msg, parse_mode="Markdown")


@authorized_only
async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /report — rapport du jour"""
    report = generate_daily_report()
    await update.message.reply_text(report, parse_mode="Markdown")


@authorized_only
async def cmd_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /weekly — rapport hebdomadaire"""
    report = generate_weekly_report()
    await update.message.reply_text(report, parse_mode="Markdown")


# ============================================================
# CALLBACKS MENU
# ============================================================

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère les callbacks du menu principal"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "boton_toggle":
        from tracking import handle_bot_toggle
        await handle_bot_toggle(query, context)

    elif data == "status_check":
        from tracking import handle_status_check
        await handle_status_check(query, context)

    elif data == "report_daily":
        report = generate_daily_report()
        await query.message.reply_text(report, parse_mode="Markdown")

    elif data == "report_weekly":
        report = generate_weekly_report()
        await query.message.reply_text(report, parse_mode="Markdown")

    elif data == "my_capital":
        capital = get_user_capital(user_id)
        mm = get_mm_summary(user_id)
        if capital == 0:
            msg = "💰 *Capital non défini*\nUtilise `/capital [montant]` pour définir ton capital.\nExemple : `/capital 5000`"
        else:
            msg = f"""
💰 *TON CAPITAL & MM*
━━━━━━━━━━━━━━━━━━━━━
💵 Capital       : `{capital}$`
📈 Profit cumulé : `{mm['profit_pct']}%`
━━━━━━━━━━━━━━━━━━━━━
{mm['level_label']}
💸 Risque/trade  : `{mm['risk_pct']}%` = `{mm['risk_amount']}$`
"""
        await query.message.reply_text(msg, parse_mode="Markdown")

    elif data == "manage_users" and is_admin(user_id):
        users = get_all_users()
        msg = f"👥 *{len(users)} abonné(s) actif(s)*\n\n"
        msg += "Commandes disponibles :\n"
        msg += "• `/adduser [id] [nom]` — Ajouter\n"
        msg += "• `/removeuser [id]` — Supprimer\n"
        msg += "• `/listusers` — Voir la liste"
        await query.message.reply_text(msg, parse_mode="Markdown")
