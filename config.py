"""
Configuration centrale du Bot RSV Trading
"""
import os

# ============================================================
# TOKENS & IDs (chargés depuis les variables d'environnement)
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# ============================================================
# PARAMÈTRES TRADING
# ============================================================
MAX_TRADES_PER_DAY = 10
MAX_LOSSES_PER_DAY = 2
MIN_RR_RATIO = 3.0  # RR minimum 1:3

# ============================================================
# MONEY MANAGEMENT — Paliers de mise
# ============================================================
MM_BASE_RISK = 0.0025       # 0.25% du capital
MM_LEVEL_1_RISK = 0.005     # 0.50% après +5% profit
MM_LEVEL_2_RISK = 0.0075    # 0.75% après +8% profit
MM_LEVEL_1_THRESHOLD = 5.0  # +5% profit
MM_LEVEL_2_THRESHOLD = 8.0  # +8% profit

# ============================================================
# RAPPORTS AUTOMATIQUES
# ============================================================
DAILY_REPORT_HOUR = 20    # Rapport quotidien à 20h
DAILY_REPORT_MINUTE = 0
WEEKLY_REPORT_DAY = 6     # Dimanche (0=Lundi, 6=Dimanche)
WEEKLY_REPORT_HOUR = 20

# ============================================================
# WEBHOOK
# ============================================================
WEBHOOK_PATH = "/webhook"
PORT = int(os.getenv("PORT", "8080"))
HOST = "0.0.0.0"
