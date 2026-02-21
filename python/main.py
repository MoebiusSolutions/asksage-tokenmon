from asksageclient import AskSageClient
from pathlib import Path
import argparse
import curses
import json
import os
import random
import sqlite3
import sys
import time

SECONDS_IN_31_DAYS = 31 * 24 * 60 * 60

def read_auth_file(auth_file_path):
    try:
        with open(auth_file_path, "r") as file:
            auth_data = json.load(file)
            email = auth_data.get("email")
            api_key = auth_data.get("api_token")
            if not email or not api_key:
                raise ValueError("The auth file must contain 'email' and 'api_token' fields.")
            return email, api_key
    except FileNotFoundError:
        raise FileNotFoundError(f"Auth file not found at {auth_file_path}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON format in auth file: {auth_file_path}")

def db_init(database_file):
    conn = sqlite3.connect(database_file)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    schema = """
    CREATE TABLE IF NOT EXISTS history (
        timestamp_epoc INTEGER PRIMARY KEY,
        monthly_inference_tokens_used INTEGER NOT NULL,
        monthly_training_tokens_used INTEGER NOT NULL
    );
    """
    conn.executescript(schema)
    return conn

def read_asksage_token_counts(client):
    monthly_inference_tokens_used = client.count_monthly_tokens()["response"]
    monthly_training_tokens_used = client.count_monthly_teach_tokens()["response"]
    return (monthly_inference_tokens_used, monthly_training_tokens_used)

def write_record_to_history(db_connection, timestamp_epoc, monthly_inference_tokens_used, monthly_training_tokens_used):
    cur = db_connection.cursor()
    cur.execute(
        "INSERT INTO history (timestamp_epoc, monthly_inference_tokens_used, monthly_training_tokens_used) VALUES (?,?,?)",
        (timestamp_epoc, monthly_inference_tokens_used, monthly_training_tokens_used)
    )
    db_connection.commit()

def get_period_deltas(
    db_connection,
    now_epoc: int,
    period_secs: int,
    period_count: int,
):
    now_aligned = (now_epoc // period_secs) * period_secs
    first_bucket = now_aligned - period_secs * (period_count - 1)

    buckets = [
        first_bucket + i * period_secs
        for i in range(period_count)
    ]

    cur = db_connection.cursor()

    # 1. Get the last reading *before* the window (baseline)
    cur.execute(
        """
        SELECT monthly_inference_tokens_used
        FROM history
        WHERE timestamp_epoc < ?
        ORDER BY timestamp_epoc DESC
        LIMIT 1
        """,
        (first_bucket,),
    )
    row = cur.fetchone()
    last_value = row[0] if row else None

    # 2. Get all readings inside the window
    cur.execute(
        """
        SELECT timestamp_epoc, monthly_inference_tokens_used
        FROM history
        WHERE timestamp_epoc >= ? AND timestamp_epoc <= ?
        ORDER BY timestamp_epoc ASC
        """,
        (first_bucket, now_epoc),
    )
    rows = cur.fetchall()

    readings_by_bucket = {b: [] for b in buckets}
    for ts, value in rows:
        bucket = (ts // period_secs) * period_secs
        if bucket in readings_by_bucket:
            readings_by_bucket[bucket].append(value)

    results = []
    seen_data = False

    for bucket in buckets:
        readings = readings_by_bucket[bucket]

        if readings:
            current_value = readings[-1]
            delta = 0 if last_value is None else current_value - last_value
            last_value = current_value
            no_data = False
        else:
            delta = 0
            no_data = True

        results.append((bucket, delta, no_data))

    return results

def format_duration(seconds):
    units = [
        ("d", 86400),
        ("h", 3600),
        ("m", 60),
        ("s", 1),
    ]

    parts = []

    for name, unit_seconds in units:
        value, seconds = divmod(seconds, unit_seconds)
        if value:
            # Use or remove
            # plural = "s" if value != 1 else ""
            # parts.append(f"{value} {name}{plural}")
            parts.append(f"{value}{name}")

    return " ".join(parts) or "0 secs"

def format_duration(period_secs, sec_per_unit, unit_name):
    value = period_secs // sec_per_unit
    return f"{value} {unit_name}"

def render_period_deltas(rows, now_epoc, period_secs, period_count, period_unit_secs, period_unit_name):
    """
    rows = list of (bucket_ts, delta, no_data)
    """
    result = ""
    for idx, (bucket_ts, delta, no_data) in enumerate(reversed(rows)):
        now_bucket = (now_epoc // period_secs) * period_secs
        bucket_age = now_bucket - bucket_ts
        bucket_age_string = format_duration(bucket_age, period_unit_secs, period_unit_name)
        bucket_age_string = bucket_age_string.rjust(8)
        if no_data:
            result += f"[+{bucket_age_string}] (no data)\n"
        else:
            result += f"[+{bucket_age_string}] {delta}\n"

    return result

def print_block_to_curses(stdscr, text, start_y=0, start_x=0):
    """
    Safely prints a multi-line string to a curses window.
    
    Args:
        stdscr: curses window
        text: a single string, possibly containing newlines
        start_y: row to start printing at
        start_x: column to start printing at
        
    Returns:
        int: number of lines actually printed
    """
    h, w = stdscr.getmaxyx()
    printed = 0

    # Split the text into lines
    lines = text.splitlines()

    for i, line in enumerate(lines):
        y = start_y + i
        if y >= h:  # stop if we run out of vertical space
            break
        try:
            stdscr.addstr(y, start_x, line[:w - start_x - 1])  # clip horizontally
            printed += 1
        except curses.error:
            pass  # ignore if writing outside bounds

    stdscr.refresh()
    return printed


# TODO: Remove or fix
# def generate_sample_data(db_connection):
#     cur = db_connection.cursor()
#
#     # Start time: 2 days ago
#     start_time = int(time.time()) - 2 * 86400
#     end_time = int(time.time())
#
#     timestamp_epoc = start_time
#     monthly_inference_tokens_used = 0
#
#     while timestamp_epoc <= end_time:
#         # Introduce gaps
#         # 20 sec gap in first minute
#         if start_time <= timestamp_epoc < start_time + 60 and timestamp_epoc % 60 in [20, 30]:
#             timestamp_epoc += 10
#             continue
#
#         # 20 min gap in first hour
#         if start_time <= timestamp_epoc < start_time + 3600 and start_time + 600 <= timestamp_epoc < start_time + 1800:
#             timestamp_epoc += 10
#             continue
#
#         # 4 hr gap in first day
#         if start_time <= timestamp_epoc < start_time + 86400 and start_time + 7200 <= timestamp_epoc < start_time + 21600:
#             timestamp_epoc += 10
#             continue
#
#         # Simulate token usage delta (random small number)
#         delta = random.randint(5, 20)
#         monthly_inference_tokens_used += delta
#         cur.execute(
#             # TODO: Separate monthly_inference_tokens_used and monthly_training_tokens_used
#             "INSERT INTO history (timestamp_epoc, monthly_inference_tokens_used, monthly_training_tokens_used) VALUES (?, ?, ?)",
#             (timestamp_epoc, monthly_inference_tokens_used, 0)
#         )
#
#         timestamp_epoc += 10  # next sample in 10s
#
#     db_connection.commit()

def main(stdscr):

    parser = argparse.ArgumentParser(description="Tracks AskSage token usage")
    parser.add_argument("--history-file", required=True, help="Path to the sqlite3 database to populate with history data.")
    parser.add_argument("--auth-file", required=True, help="Path to the JSON file containing email and API key.")
    parser.add_argument("--user-base-url", default="https://api.asksage.ai/user", help="Base URL for the Ask Sage user API.")
    parser.add_argument("--server-base-url", default="https://api.asksage.ai/server", help="Base URL for the Ask Sage server API.")
    parser.add_argument("--gen-sample-data", action=argparse.BooleanOptionalAction, default=False, help="Skip all other actions and write sample data to the database")
    args = parser.parse_args()

    history_file = args.history_file
    db_connection = db_init(history_file)

    curses.curs_set(0)

    if args.gen_sample_data:
        print("Writing sample data to database file")
        generate_sample_data(db_connection)
        return

        # TODO: Where did this come from? Bad paste?
        if no_data:
            stdscr.addstr(idx+1, 0, f"[+{bucket_age_string}] (no data)")
        else:
            stdscr.addstr(idx+1, 0, f"[+{bucket_age_string}] {delta}")

    stdscr.clear()
    stdscr.addstr(1, 0, f"Reading first data point...")
    stdscr.refresh()

    while True: 
        email, api_key = read_auth_file(args.auth_file)
        client = AskSageClient(
            email=email,
            api_key=api_key,
            user_base_url=args.user_base_url,
            server_base_url=args.server_base_url
        )
        (monthly_inference_tokens_used, monthly_training_tokens_used) = read_asksage_token_counts(client)

        now_epoc = int(time.time())
        write_record_to_history(db_connection, now_epoc, monthly_inference_tokens_used, monthly_training_tokens_used)

        out_text = ""
        deltas = get_period_deltas(db_connection, now_epoc, 10, 6)
        out_text += render_period_deltas(deltas, now_epoc, 10, 6, 1, "secs")
        out_text += "---------\n"
        deltas = get_period_deltas(db_connection, now_epoc, 600, 6)
        out_text += render_period_deltas(deltas, now_epoc, 600, 6, 60, "mins")
        out_text += "---------\n"
        deltas = get_period_deltas(db_connection, now_epoc, 3600, 6)
        out_text += render_period_deltas(deltas, now_epoc, 3600, 6, 3600, "hours")
        out_text += "---------\n"
        deltas = get_period_deltas(db_connection, now_epoc, 86400, 7)
        out_text += render_period_deltas(deltas, now_epoc, 86400, 7, 86400, "days")
        stdscr.clear()
        print_block_to_curses(stdscr, out_text)
        stdscr.refresh()

        # Sleep slightly less than 10 seconds (our smallest bucket)
        time.sleep(7)

if __name__ == "__main__":
    curses.wrapper(main)

