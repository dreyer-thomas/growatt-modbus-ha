"""Konstanten der Integration Growatt SPH (lokal)."""
from __future__ import annotations

DOMAIN = "growatt_sph_local"
MANUFACTURER = "Growatt"

CONF_SLAVE = "slave"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_ALLOW_WRITE = "allow_write"

DEFAULT_PORT = 502
DEFAULT_SLAVE = 1
DEFAULT_SCAN_INTERVAL = 10
MIN_SCAN_INTERVAL = 5
# Holding-Register (Einstellungen) nur alle N Zyklen lesen
SETTINGS_EVERY_N = 6

# Leseblöcke (max. 125 Register pro Anfrage; Growatt verträgt <= 125)
INPUT_BLOCKS: tuple[tuple[int, int], ...] = ((0, 100), (1000, 64))
SETTINGS_BLOCKS: tuple[tuple[int, int], ...] = ((608, 1), (1037, 1), (1090, 3), (1100, 3))
INFO_BLOCK = (0, 45)       # Holding 0..44: Firmware, Seriennummer, Typ, Phasen
PROTOCOL_REGISTER = 88     # Holding: Modbus-Protokollversion x100

# Schreibbare Register
REG_LOAD_FIRST_STOP_SOC = 608   # Backup-Reserve: Entladestopp im Load-First-Betrieb
REG_BF_CHARGE_RATE = 1090       # Ladeleistung im Battery-First-Betrieb (%)
REG_BF_STOP_SOC = 1091          # Battery First: laden bis Ladestand (%)
REG_AC_CHARGE = 1092            # Netzladen im Battery-First-Fenster
REG_BF1_START = 1100            # Battery-First-Fenster 1: Start, Ende, Aktiv
REG_BF1_END = 1101
REG_BF1_ENABLE = 1102
FULL_DAY_START = 0              # 00:00
FULL_DAY_END = (23 << 8) | 59   # 23:59 -> 5947

BACKUP_SOC_MIN = 10
BACKUP_SOC_MAX = 100
GRID_CHARGE_SOC_MIN = 10
GRID_CHARGE_SOC_MAX = 100
CHARGE_RATE_MIN = 5
CHARGE_RATE_MAX = 100

STATUS_OPTIONS = ["waiting", "normal", "fault", "flash", "normal_hybrid", "unknown"]
STATUS_MAP = {0: "waiting", 1: "normal", 2: "normal", 3: "fault", 4: "flash",
              5: "normal_hybrid", 6: "normal_hybrid", 7: "normal_hybrid", 8: "normal_hybrid"}
CT_MODE_OPTIONS = ["wired_ct", "wireless_ct", "meter", "unknown"]
CT_MODE_MAP = {0: "wired_ct", 1: "wireless_ct", 2: "meter", 3: "meter"}
