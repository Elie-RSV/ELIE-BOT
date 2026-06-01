"""
Money Management — Calcul automatique des lots et risques
Paliers : 0.25% / 0.50% / 0.75% selon profit cumulé
"""
from config import (
    MM_BASE_RISK, MM_LEVEL_1_RISK, MM_LEVEL_2_RISK,
    MM_LEVEL_1_THRESHOLD, MM_LEVEL_2_THRESHOLD,
    MIN_RR_RATIO
)
from database import get_user_capital, get_user_profit_pct


def get_risk_percentage(user_id: int) -> float:
    """Retourne le % de risque selon le palier de profit atteint"""
    profit_pct = get_user_profit_pct(user_id)

    if profit_pct >= MM_LEVEL_2_THRESHOLD:
        return MM_LEVEL_2_RISK   # 0.75%
    elif profit_pct >= MM_LEVEL_1_THRESHOLD:
        return MM_LEVEL_1_RISK   # 0.50%
    else:
        return MM_BASE_RISK      # 0.25%


def get_risk_label(user_id: int) -> str:
    """Retourne le label du palier actuel"""
    profit_pct = get_user_profit_pct(user_id)
    if profit_pct >= MM_LEVEL_2_THRESHOLD:
        return "🔥 Palier 3 — 0.75%"
    elif profit_pct >= MM_LEVEL_1_THRESHOLD:
        return "⚡ Palier 2 — 0.50%"
    else:
        return "🛡️ Palier 1 — 0.25%"


def calculate_lot(user_id: int, entry: float, sl: float, pair: str = "XAUUSD") -> float:
    """
    Calcule le lot selon :
    - Capital de l'utilisateur
    - % de risque selon palier
    - Distance entre entrée et SL
    """
    capital = get_user_capital(user_id)
    if capital <= 0:
        return 0.01  # Lot minimum par défaut

    risk_pct = get_risk_percentage(user_id)
    risk_amount = capital * risk_pct  # Montant en $ à risquer

    sl_distance = abs(entry - sl)
    if sl_distance == 0:
        return 0.01

    # Valeur du pip selon la paire
    pip_value = get_pip_value(pair)

    # Calcul du lot
    lot = risk_amount / (sl_distance * pip_value)
    lot = round(max(0.01, lot), 2)  # Minimum 0.01 lot

    return lot


def calculate_pnl(lot: float, entry: float, target: float, pair: str = "XAUUSD") -> float:
    """Calcule le PnL estimé en $"""
    pip_value = get_pip_value(pair)
    distance = abs(target - entry)
    return round(lot * distance * pip_value, 2)


def calculate_rr(entry: float, tp: float, sl: float) -> float:
    """Calcule le Risk/Reward ratio"""
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    if risk == 0:
        return 0
    return round(reward / risk, 2)


def is_rr_valid(entry: float, tp: float, sl: float) -> bool:
    """Vérifie si le RR respecte le minimum 1:3"""
    rr = calculate_rr(entry, tp, sl)
    return rr >= MIN_RR_RATIO


def get_pip_value(pair: str) -> float:
    """Valeur d'un pip par lot standard selon la paire"""
    pip_values = {
        "XAUUSD": 1.0,     # Gold — 1$ par pip par 0.01 lot
        "EURUSD": 10.0,
        "GBPUSD": 10.0,
        "USDJPY": 9.0,
        "USDCHF": 10.0,
        "AUDUSD": 10.0,
        "NAS100": 1.0,
        "US30":   1.0,
        "DAX":    1.0,
    }
    return pip_values.get(pair.upper(), 10.0)


def get_mm_summary(user_id: int) -> dict:
    """Retourne un résumé complet du MM pour l'utilisateur"""
    capital = get_user_capital(user_id)
    profit_pct = get_user_profit_pct(user_id)
    risk_pct = get_risk_percentage(user_id)
    risk_amount = capital * risk_pct if capital > 0 else 0

    return {
        "capital": capital,
        "profit_pct": round(profit_pct, 2),
        "risk_pct": risk_pct * 100,
        "risk_amount": round(risk_amount, 2),
        "level_label": get_risk_label(user_id),
        "next_level": MM_LEVEL_1_THRESHOLD if profit_pct < MM_LEVEL_1_THRESHOLD
                      else MM_LEVEL_2_THRESHOLD if profit_pct < MM_LEVEL_2_THRESHOLD
                      else None
    }
