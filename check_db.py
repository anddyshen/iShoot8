import sqlite3, os

db_path = os.path.join('instance', 'ishoot.db')
conn = sqlite3.connect(db_path)
cur = conn.cursor()

print('=== UserFavorites ===')
cur.execute('SELECT id, created_at FROM user_favorites ORDER BY id')
for row in cur.fetchall():
    print(f'  ID={row[0]}: created_at={row[1]}')

print()
print('=== UserPurchasedTickets ===')
cur.execute('SELECT id, created_at FROM user_purchased_tickets ORDER BY id')
for row in cur.fetchall():
    print(f'  ID={row[0]}: created_at={row[1]}')

conn.close()
