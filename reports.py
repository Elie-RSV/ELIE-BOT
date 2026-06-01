"""
Module Rapports — Rapports quotidiens et hebdomadaires automatiques
Analyse de performance, taux de réussite, bilan
"""
import logging
from datetime import date, timedelta
from telegram import Bot
from database import (
    get_today_trades, get_week_trades, get_today_session,
    get_all_users, update_session
)
from config import ADMIN_ID

logger = logging.getLogger(__name__)


# ============================================================
# RAPPORT QUOTIDIEN
# ============================================================

def generate_daily_report() -> str:
    """Génère le rapport quotidien complet"""
    trades = get_today_trades()
    session = get_today_session()
    today = date.today().strftime("%d/%m/%Y")

    total = len(trades)
    wins = len([t for t in trades if t["status"] == "win"])
    losses = len([t for t in trades if t["status"] == "loss"])
    be_trades = len([t for t in trades if t["status"] == "be"])
    open_trades = len([t for t in trades if t["status"] == "open"])

    win_rate = round((wins / total * 100), 1) if total > 0 else 0
    loss_rate = round((losses / total * 100), 1) if total > 0 else 0
    total_pnl = session["total_pnl"]
    pnl_emoji = "💰" if total_pnl >= 0 else "💸"

    # Analyse qualitative
    analysis = generate_daily_analysis(trades, session)

    report = f"""
📊 *RAPPORT QUOTIDIEN — {today}*
━━━━━━━━━━━━━━━━━━━━━━━━━
📈 *PERFORMANCE DU JOUR*
━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Trades total    : *{total}/10*
✅ Wins            : *{wins}*
❌ Losses          : *{losses}*
⚖️ Break Even      : *{be_trades}*
🔓 En cours        : *{open_trades}*
━━━━━━━━━━━━━━━━━━━━━━━━━
📈 Taux de réussite : *{win_rate}%*
📉 Taux d'échec     : *{loss_rate}%*
{pnl_emoji} PnL total        : *{'+' if total_pnl >= 0 else ''}{round(total_pnl, 2)}$*
━━━━━━━━━━━━━━━━━━━━━━━━━
📋 *DÉTAIL DES TRADES*
━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    for i, trade in enumerate(trades, 1):
        status_emoji = {"win": "✅", "loss": "❌", "be": "⚖️", "open": "🔓"}.get(trade["status"], "❓")
        pnl_str = f"+{round(trade['pnl'], 2)}$" if trade["pnl"] >= 0 else f"{round(trade['pnl'], 2)}$"
        report += f"{i}. {status_emoji} `{trade['pair']}` *{trade['direction']}* — RR `1:{trade['rr']}` — {pnl_str}\n"

    report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━
🧠 *ANALYSE & BILAN*
━━━━━━━━━━━━━━━━━━━━━━━━━
{analysis}
━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 *PRÉPARATION DEMAIN*
━━━━━━━━━━━━━━━━━━━━━━━━━
📌 Revoir les zones importantes d'aujourd'hui
📌 Identifier les niveaux clés pour demain
📌 Vérifier la corrélation HTF avant toute entrée
📌 Patience — attendre la prise de liquidité
━━━━━━━━━━━━━━━━━━━━━━━━━
💪 *Bonne nuit. On revient plus fort demain.*
"""
    return report.strip()


def generate_daily_analysis(trades: list, session: dict) -> str:
    """Génère une analyse qualitative automatique"""
    if not trades:
        return "📭 Aucun trade aujourd'hui."

    wins = [t for t in trades if t["status"] == "win"]
    losses = [t for t in trades if t["status"] == "loss"]
    win_rate = len(wins) / len(trades) * 100 if trades else 0

    analysis_lines = []

    if win_rate >= 70:
        analysis_lines.append("🔥 Excellente journée — stratégie bien appliquée")
    elif win_rate >= 50:
        analysis_lines.append("✅ Bonne journée — quelques améliorations possibles")
    elif win_rate >= 30:
        analysis_lines.append("⚠️ Journée difficile — revoir les entrées")
    else:
        analysis_lines.append("🛑 Journée compliquée — analyse approfondie nécessaire")

    # Analyse des scores
    avg_score = sum(t["score"] for t in trades) / len(trades) if trades else 0
    if avg_score < 3:
        analysis_lines.append("📉 Score moyen faible — filtrer davantage les setups")
    elif avg_score >= 4:
        analysis_lines.append("⭐ Bons setups sélectionnés — continuer dans cette direction")

    # Analyse pertes
    if losses:
        for loss in losses:
            if loss["rr"] < 2:
                analysis_lines.append("⚠️ RR trop faible sur certaines entrées — respecter le 1:3 minimum")
                break

    return "\n".join(f"• {line}" for line in analysis_lines)


# ============================================================
# RAPPORT HEBDOMADAIRE
# ============================================================

def generate_weekly_report() -> str:
    """Génère le rapport hebdomadaire"""
    trades = get_week_trades()
    week_start = (date.today() - timedelta(days=6)).strftime("%d/%m")
    week_end = date.today().strftime("%d/%m/%Y")

    total = len(trades)
    wins = len([t for t in trades if t["status"] == "win"])
    losses = len([t for t in trades if t["status"] == "loss"])
    be_trades = len([t for t in trades if t["status"] == "be"])

    win_rate = round((wins / total * 100), 1) if total > 0 else 0
    loss_rate = round((losses / total * 100), 1) if total > 0 else 0
    total_pnl = sum(t["pnl"] for t in trades)
    pnl_emoji = "💰" if total_pnl >= 0 else "💸"

    # Meilleure et pire session
    best_trade = max(trades, key=lambda t: t["pnl"]) if trades else None
    worst_trade = min(trades, key=lambda t: t["pnl"]) if trades else None

    report = f"""
📅 *RAPPORT HEBDOMADAIRE*
*{week_start} → {week_end}*
━━━━━━━━━━━━━━━━━━━━━━━━━
📊 *BILAN DE LA SEMAINE*
━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Trades total    : *{total}*
✅ Wins            : *{wins}*
❌ Losses          : *{losses}*
⚖️ Break Even      : *{be_trades}*
━━━━━━━━━━━━━━━━━━━━━━━━━
📈 Taux de réussite : *{win_rate}%*
📉 Taux d'échec     : *{loss_rate}%*
{pnl_emoji} PnL total        : *{'+' if total_pnl >= 0 else ''}{round(total_pnl, 2)}$*
━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    if best_trade:
        report += f"🏆 *Meilleur trade* : `{best_trade['pair']}` +{round(best_trade['pnl'], 2)}$\n"
    if worst_trade:
        report += f"💸 *Pire trade*     : `{worst_trade['pair']}` {round(worst_trade['pnl'], 2)}$\n"

    report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━
🧠 *RECOMMANDATIONS*
━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    # Recommandations automatiques
    if win_rate >= 70:
        report += "• 🔥 Excellente semaine — maintenir cette discipline\n"
        report += "• ✅ La stratégie SMC/ICT est bien appliquée\n"
    elif win_rate >= 50:
        report += "• ✅ Semaine correcte — continuer à filtrer les setups\n"
        report += "• 📌 Revoir les entrées sur les trades perdants\n"
    else:
        report += "• ⚠️ Semaine difficile — faire un backtest approfondi\n"
        report += "• 📌 Vérifier la corrélation HTF/LTF sur chaque entrée\n"
        report += "• 🎯 Attendre uniquement les setups A+ la semaine prochaine\n"

    report += """
━━━━━━━━━━━━━━━━━━━━━━━━━
💪 *Bonne semaine à venir. Discipline & Patience.*
"""
    return report.strip()


# ============================================================
# ENVOI AUTOMATIQUE
# ============================================================

async def send_daily_report(bot: Bot):
    """Envoie le rapport quotidien à tous les utilisateurs"""
    try:
        report = generate_daily_report()
        users = get_all_users()

        await bot.send_message(chat_id=ADMIN_ID, text=report, parse_mode="Markdown")

        for user in users:
            try:
                await bot.send_message(
                    chat_id=user["user_id"],
                    text=report,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Erreur rapport user {user['user_id']}: {e}")

        logger.info("✅ Rapport quotidien envoyé")
    except Exception as e:
        logger.error(f"Erreur génération rapport: {e}")


async def send_weekly_report(bot: Bot):
    """Envoie le rapport hebdomadaire à tous les utilisateurs"""
    try:
        report = generate_weekly_report()
        users = get_all_users()

        await bot.send_message(chat_id=ADMIN_ID, text=report, parse_mode="Markdown")

        for user in users:
            try:
                await bot.send_message(
                    chat_id=user["user_id"],
                    text=report,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Erreur rapport hebdo user {user['user_id']}: {e}")

        logger.info("✅ Rapport hebdomadaire envoyé")
    except Exception as e:
        logger.error(f"Erreur génération rapport hebdo: {e}")
