import sqlite3, os
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'loanmvp.db')

def send_message(sender, receiver, body):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT, receiver TEXT, body TEXT)')
    c.execute('INSERT INTO messages (sender, receiver, body) VALUES (?,?,?)', (sender, receiver, body))
    conn.commit()
    conn.close()

def fetch_messages(user):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT, receiver TEXT, body TEXT)')
    c.execute('SELECT sender, body FROM messages WHERE receiver=? ORDER BY id DESC', (user,))
    rows = c.fetchall()
    conn.close()
    return rows
