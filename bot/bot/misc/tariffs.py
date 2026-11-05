from bot.misc.util import CONFIG

TRIAL_DATA_LIMIT_GB = 50
PAID_DATA_LIMIT_GB_BY_MONTH = {
    1: 300,
    3: 600,
    6: 1000,
    12: 0,
}


def get_trial_data_limit_gb() -> int:
    return TRIAL_DATA_LIMIT_GB


def get_paid_data_limit_gb(month_count: int | None) -> int:
    if month_count is None:
        return CONFIG.limit_GB
    return PAID_DATA_LIMIT_GB_BY_MONTH.get(int(month_count), CONFIG.limit_GB)
