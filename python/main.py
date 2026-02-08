from asksageclient import AskSageClient
import argparse
import json
import os
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

def ensure_history_file_exists(history_file):
    if os.path.exists(history_file):
        return
    os.makedirs(os.path.dirname(history_file) or ".", exist_ok=True)
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump([], f)

# Reads the history of token count changes from a json file on disk.
#
# The json format is list of objects, with each object containing:
# * timestamp_epoc
# * monthly_inference_tokens_used
# * monthly_training_tokens_used
#
# The list is sorted before return, with oldest timestamps first.
def read_history_from_disk(history_file):
    with open(history_file, "r", encoding="utf-8") as f:
        history = json.load(f)
    history.sort(key=lambda x: x.get("timestamp_epoc", 0))
    return history

# Updates the history list (as returned from read_history_from_disk),
# adding the new reading and maintaining sorting order of oldest timestamps first,
# but only if the monthly_inference_tokens_used or monthly_training_tokens_used
# value has changed since the previous record.
def add_to_history(history, timestamp_epoc,
                   monthly_inference_tokens_used,
                   monthly_training_tokens_used):
    timestamp_epoc = int(timestamp_epoc)
    monthly_inference_tokens_used = int(monthly_inference_tokens_used)
    monthly_training_tokens_used = int(monthly_training_tokens_used)
    if history:
        # Ensure correct order before comparison
        history.sort(key=lambda x: x["timestamp_epoc"])
        last = history[-1]
        if (last.get("monthly_inference_tokens_used") == monthly_inference_tokens_used and
                last.get("monthly_training_tokens_used") == monthly_training_tokens_used):
            return  # No change; do not add a new record
    history.append({
        "timestamp_epoc": timestamp_epoc,
        "monthly_inference_tokens_used": monthly_inference_tokens_used,
        "monthly_training_tokens_used": monthly_training_tokens_used,
    })
    history.sort(key=lambda x: x["timestamp_epoc"])


# Updates the history list (as returned from read_history_from_disk),
# deleting all entries that are older than 31 days.
def prune_history(history, timestamp_epoc):
    cutoff = int(timestamp_epoc) - SECONDS_IN_31_DAYS
    history[:] = [
        entry for entry in history
        if entry.get("timestamp_epoc", 0) >= cutoff
    ]

# Writes the history list (as returned from read_history_from_disk),
# to disk as a json file.
def write_history_to_disk(history, history_file):
    tmp_file = f"{history_file}.tmp"
    os.makedirs(os.path.dirname(history_file) or ".", exist_ok=True)
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, sort_keys=True)
    os.replace(tmp_file, history_file)

# Reads the current monthly count of inference and training tokens used
def read_asksage_token_counts(client):
    monthly_inference_tokens_used = client.count_monthly_tokens()["response"]
    monthly_training_tokens_used = client.count_monthly_teach_tokens()["response"]
    return (monthly_inference_tokens_used, monthly_training_tokens_used)

# Example usage in main()
def main():
    parser = argparse.ArgumentParser(description="Sync files from a local directory to an Ask Sage dataset.")
    parser.add_argument("--history-dir", required=True, help="Path to the directory history is to be stored.")
    parser.add_argument("--auth-file", required=True, help="Path to the JSON file containing email and API key.")
    parser.add_argument("--user-base-url", default="https://api.asksage.ai/user", help="Base URL for the Ask Sage user API.")
    parser.add_argument("--server-base-url", default="https://api.asksage.ai/server", help="Base URL for the Ask Sage server API.")
    args = parser.parse_args()

    email, api_key = read_auth_file(args.auth_file)
    client = AskSageClient(
        email=email,
        api_key=api_key,
        user_base_url=args.user_base_url,
        server_base_url=args.server_base_url
    )
    (monthly_inference_tokens_used,monthly_training_tokens_used) = read_asksage_token_counts(client)

    history_file = args.history_dir + "/history.json"
    ensure_history_file_exists(history_file)
    history = read_history_from_disk(history_file)
    now_epoc = int(time.time())
    add_to_history(
        history,
        now_epoc,
        monthly_inference_tokens_used,
        monthly_training_tokens_used,
    )
    prune_history(history, now_epoc)
    write_history_to_disk(history, history_file)

if __name__ == "__main__":
    main()

