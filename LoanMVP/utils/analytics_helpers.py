import sqlite3, os
import statistics

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'loanmvp.db')

def loan_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT status FROM loans')
    statuses = [r[0] for r in c.fetchall()]
    conn.close()
    return {
        'total': len(statuses),
        'approved': statuses.count('Approved'),
        'processing': statuses.count('Processing'),
        'review': statuses.count('In Review')
    }

def avg_loan_amount():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT amount FROM loans')
    amounts = [r[0] for r in c.fetchall()]
    conn.close()
    return round(statistics.mean(amounts), 2) if amounts else 0
