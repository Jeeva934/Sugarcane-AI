import sys
sys.path.insert(0, "backend")
from app.services.security import hash_password
import sqlite3

new_pw = "Test12345678!"
new_hash = hash_password(new_pw)

conn = sqlite3.connect("backend/sugarcane.db")
c = conn.cursor()
c.execute("UPDATE users SET password_hash = ? WHERE email = 'test1@example.com'", (new_hash,))
conn.commit()
print("SUCCESS: Password for test1@example.com set to:", new_pw)

