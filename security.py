"""
Sécurité — Filtrage strict par user_id
Aucune commande ne passe sans vérification
"""
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_ID
from database import user_exists, get_user
import logging

logger = logging.getLogger(__name__)


def admin_only(func):
    """Décorateur — Réservé à l'Admin uniquement"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            logger.warning(f"⛔ Accès refusé — user_id: {user_id}")
            await update.message.reply_text(
                "⛔ *Accès refusé.*\nTu n'es pas autorisé à utiliser cette commande.",
                parse_mode="Markdown"
            )
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


def authorized_only(func):
    """Décorateur — Réservé aux utilisateurs autorisés (admin + abonnés)"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID and not user_exists(user_id):
            logger.warning(f"⛔ Utilisateur non autorisé — user_id: {user_id}")
            await update.message.reply_text(
                "⛔ *Accès non autorisé.*\nContacte l'administrateur pour obtenir l'accès.",
                parse_mode="Markdown"
            )
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def is_authorized(user_id: int) -> bool:
    return user_id == ADMIN_ID or user_exists(user_id)
