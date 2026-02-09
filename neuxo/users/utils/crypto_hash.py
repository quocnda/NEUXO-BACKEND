from cryptography.fernet import Fernet
import os

# Load key từ biến môi trường hoặc file
FERNET_KEY = os.getenv("FERNET_KEY")

if not FERNET_KEY:
    raise Exception("FERNET_KEY is not set")

fernet = Fernet(FERNET_KEY)


def encrypt_password(password: str) -> str:
    return fernet.encrypt(password.encode()).decode()


def decrypt_password(encrypted_password: str) -> str:
    return fernet.decrypt(encrypted_password.encode()).decode()
