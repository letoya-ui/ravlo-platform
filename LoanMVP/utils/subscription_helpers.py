import sqlite3, os
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'loanmvp.db')

PLANS = {
    'starter': {'price': 0, 'features': ['basic dashboard']},
    'pro': {'price': 49, 'features': ['ai assistant', 'messaging', 'crm']},
    'enterprise': {'price': 99, 'features': ['all features', 'white label']}
}

def get_user_plan(user_email):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS subscriptions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, plan TEXT)')
    c.execute('SELECT plan FROM subscriptions WHERE user_email=?', (user_email,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 'starter'

def set_user_plan(user_email, plan):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS subscriptions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, plan TEXT)')
    c.execute('INSERT INTO subscriptions (user_email, plan) VALUES (?,?)', (user_email, plan))
    conn.commit()
    conn.close()
