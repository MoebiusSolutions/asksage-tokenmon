from contextlib import redirect_stdout
from main import db_init, write_record_to_history, get_period_deltas, print_period_deltas
from pathlib import Path
import io
import pytest
import sqlite3
import time

@pytest.fixture
def db_conn(tmp_path: Path):
    db_file = tmp_path / "test.db"
    conn = db_init(str(db_file))
    yield conn
    conn.close()

# def test_basic_10s_deltas(db_conn):
#     now = 1_000_000_025
#
#     write_record_to_history(db_conn, 1_000_000_002, 100, 0)
#     write_record_to_history(db_conn, 1_000_000_013, 110, 0)
#     write_record_to_history(db_conn, 1_000_000_021, 130, 0)
#
#     rows = get_period_deltas(
#         db_connection=db_conn,
#         now_epoc=now,
#         period_secs=10,
#         period_count=3,
#     )
#
#     assert rows == [
#         (1_000_000_000, 0),
#         (1_000_000_010, 10),
#         (1_000_000_020, 20),
#     ]
#
# def test__get_period_deltas__gap_rollup(db_conn):
#     now = 1_000_000_060
#
#     write_record_to_history(db_conn, 1_000_000_000, 100, 0)
#     # gap: 10s + 20s missing
#     write_record_to_history(db_conn, 1_000_000_030, 160, 0)
#
#     rows = get_period_deltas(
#         db_connection=db_conn,
#         now_epoc=now,
#         period_secs=10,
#         period_count=4,
#     )
#
#     assert rows == [
#         (1_000_000_030, 60),
#     ]
#
# def test__get_period_deltas__no_data(db_conn):
#     now = 1_000_000_000
#
#     rows = get_period_deltas(
#         db_connection=db_conn,
#         now_epoc=now,
#         period_secs=10,
#         period_count=5,
#     )
#
#     assert rows == []
#
# def test__print_period_deltas__contiguous():
#     rows = [
#         (100, 0),
#         (110, 10),
#         (120, 20),
#     ]
#     now_epoc = 120
#     period_secs = 10
#     period_count = 3
#
#     f = io.StringIO()
#     with redirect_stdout(f):
#         print_period_deltas(rows, now_epoc, period_secs, period_count)
#
#     output = f.getvalue().strip().splitlines()
#     expected = [
#         "100, 0",
#         "110, 10",
#         "120, 20",
#     ]
#     assert output == expected
#
# def test__print_period_deltas__with_gaps():
#     rows = [
#         (100, 0),
#         (120, 20),  # 110 missing
#     ]
#     now_epoc = 120
#     period_secs = 10
#     period_count = 3
#
#     f = io.StringIO()
#     with redirect_stdout(f):
#         print_period_deltas(rows, now_epoc, period_secs, period_count)
#
#     output = f.getvalue().strip().splitlines()
#     expected = [
#         "100, 0",
#         "110, no data",
#         "120, 20",
#     ]
#     assert output == expected
#
# def test__print_period_deltas__first_bucket_missing():
#     rows = [
#         (110, 5),
#         (120, 15),
#     ]
#     now_epoc = 120
#     period_secs = 10
#     period_count = 3
#
#     f = io.StringIO()
#     with redirect_stdout(f):
#         print_period_deltas(rows, now_epoc, period_secs, period_count)
#
#     output = f.getvalue().strip().splitlines()
#     expected = [
#         "100, no data",
#         "110, 5",
#         "120, 15",
#     ]
#     assert output == expected
#

def test_basic_10s_deltas(db_conn):
    now = 1_000_000_025

    write_record_to_history(db_conn, 1_000_000_002, 100, 0)
    write_record_to_history(db_conn, 1_000_000_013, 110, 0)
    write_record_to_history(db_conn, 1_000_000_021, 130, 0)

    rows = get_period_deltas(
        db_connection=db_conn,
        now_epoc=now,
        period_secs=10,
        period_count=3,
    )

    assert rows == [
        (1_000_000_000, 0, False),
        (1_000_000_010, 10, False),
        (1_000_000_020, 20, False),
    ]

def test__get_period_deltas__gap_rollup(db_conn):
    now = 1_000_000_060

    write_record_to_history(db_conn, 1_000_000_000, 100, 0)
    # gap: 10s + 20s missing
    write_record_to_history(db_conn, 1_000_000_030, 160, 0)

    rows = get_period_deltas(
        db_connection=db_conn,
        now_epoc=now,
        period_secs=10,
        period_count=4,
    )

    assert rows == [
        (1_000_000_030, 60, False),  # rolled delta
        (1_000_000_040, 0, True),
        (1_000_000_050, 0, True),
        (1_000_000_060, 0, True),
    ]

def test__get_period_deltas__no_data(db_conn):
    now = 1_000_000_000

    rows = get_period_deltas(
        db_connection=db_conn,
        now_epoc=now,
        period_secs=10,
        period_count=5,
    )

    assert rows == [
        (999_999_960, 0, True),
        (999_999_970, 0, True),
        (999_999_980, 0, True),
        (999_999_990, 0, True),
        (1_000_000_000, 0, True),
    ]

def test__print_period_deltas__contiguous():
    rows = [
        (100, 0, False),
        (110, 10, False),
        (120, 20, False),
    ]

    f = io.StringIO()
    with redirect_stdout(f):
        print_period_deltas(rows, None, None, None)

    output = f.getvalue().strip().splitlines()
    assert output == [
        "100, 0",
        "110, 10",
        "120, 20",
    ]

def test__print_period_deltas__with_gaps():
    rows = [
        (100, 0, False),
        (110, 0, True),
        (120, 20, False),
    ]

    f = io.StringIO()
    with redirect_stdout(f):
        print_period_deltas(rows, None, None, None)

    output = f.getvalue().strip().splitlines()
    assert output == [
        "100, 0",
        "110, no data",
        "120, 20",
    ]

def test__print_period_deltas__first_bucket_missing():
    rows = [
        (100, 0, True),
        (110, 5, False),
        (120, 15, False),
    ]

    f = io.StringIO()
    with redirect_stdout(f):
        print_period_deltas(rows, None, None, None)

    output = f.getvalue().strip().splitlines()
    assert output == [
        "100, no data",
        "110, 5",
        "120, 15",
    ]

def test__get_and_print_period_deltas__integration(db_conn):
    now = 1_000_000_090
    period_secs = 10
    period_count = 7  # buckets: 30 → 90

    # Seed history with uneven samples and gaps
    write_record_to_history(db_conn, 1_000_000_031, 100, 0)
    write_record_to_history(db_conn, 1_000_000_044, 120, 0)   # same bucket
    write_record_to_history(db_conn, 1_000_000_061, 150, 0)
    # gap at 70
    write_record_to_history(db_conn, 1_000_000_081, 210, 0)

    rows = get_period_deltas(
        db_connection=db_conn,
        now_epoc=now,
        period_secs=period_secs,
        period_count=period_count,
    )

    f = io.StringIO()
    with redirect_stdout(f):
        print_period_deltas(rows, now, period_secs, period_count)

    output = f.getvalue().strip().splitlines()

    assert output == [
        "1000000030, 0",        # first observed bucket
        "1000000040, 20",       # rolled inside bucket
        "1000000050, no data",
        "1000000060, 30",
        "1000000070, no data",
        "1000000080, 60",
        "1000000090, no data",
    ]

