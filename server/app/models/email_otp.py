"""EmailOTP table schema (DynamoDB).

Table: email_otps
PK: user_id (N)
SK: id (N) — auto-increment via counters table

Fields:
    id: int
    user_id: int
    code: str  (6-digit OTP)
    expires_at: str (ISO datetime)
    is_used: bool
    created_at: str (ISO datetime)
"""
TABLE_NAME = "email_otps"
