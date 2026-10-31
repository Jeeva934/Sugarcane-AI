import sys
sys.path.insert(0, "backend")
from app.services.security import verify_password
import sqlite3

conn = sqlite3.connect("backend/sugarcane.db")
c = conn.cursor()
c.execute("SELECT password_hash FROM users WHERE email='test1@example.com'")
row = c.fetchone()
if not row:
    print("User not found")
    sys.exit(0)

pw_hash = row[0]

candidates = [
    "123456789012", "test12345678", "Test12345678", "Test12345678!", "test12345678!",
    "Password1234", "Password1234!", "password1234", "password1234!",
    "a-strong-password-123", "a-strong-password", "test1test1test1", "Test1Test1Test1",
    "sugarcane123!", "Sugarcane123!", "sugarcane1234", "Sugarcane1234",
    "FarmerPassword123!", "farmerpassword123", "Farmer12345678",
    "Test1@example.com", "test1@example.com", "Test1password", "Test1Password!",
    "1234567890123", "012345678901", "qwertyuiopas", "QWERTYUIOPAS",
    "password12345", "Password12345", "Password12345!",
    "Test1@123456", "test1@123456", "Test@12345678", "Password@1234",
    "123456781234", "test1test1test", "test11111111", "test12341234"
]

for cand in candidates:
    if verify_password(cand, pw_hash):
        print("MATCH FOUND:", cand)
        sys.exit(0)

print("Not found in this list")
