# 2023 Data (Mocked/Static based on typical distribution for demo)
# In a real scenario, this would be a full export.
# Format: { "YYYY-MM-DD": count }
DATA_2023 = {
    "2023-01-01": 5, "2023-01-07": 12, "2023-01-14": 15, "2023-01-20": 8,
    "2023-02-04": 20, "2023-02-14": 25, "2023-02-25": 18,
    "2023-03-08": 10, "2023-03-15": 12, "2023-03-22": 14,
    "2023-04-01": 22, "2023-04-15": 30, "2023-04-29": 45, # Holiday peak
    "2023-05-01": 50, "2023-05-02": 48, "2023-05-20": 40,
    "2023-06-01": 15, "2023-06-18": 35,
    "2023-07-01": 25, "2023-07-15": 28, "2023-07-29": 32,
    "2023-08-05": 35, "2023-08-12": 38, "2023-08-19": 42,
    "2023-09-09": 20, "2023-09-29": 40, "2023-09-30": 55,
    "2023-10-01": 60, "2023-10-02": 58, "2023-10-03": 55, # Golden Week
    "2023-11-11": 25, "2023-11-25": 18,
    "2023-12-24": 45, "2023-12-25": 40, "2023-12-31": 65  # NYE
}

def get_2023_data():
    """Return list of [date_str, count] for 2023."""
    # Expand to fill a bit more "realistic" scattered data
    # (Optional: algorithmic expansion could go here)
    return [[k, v] for k, v in DATA_2023.items()]
