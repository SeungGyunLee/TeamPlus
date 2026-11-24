"""비밀번호 해시와 로그인 토큰.

- 비밀번호: 표준 라이브러리 hashlib.scrypt (외부 패키지 없음). 평문은 어디에도 저장하지 않는다.
- 토큰: 무작위 문자열을 발급하고 DB에는 SHA-256 해시만 저장한다.
  유출된 DB만으로는 로그인할 수 없고, 로그아웃하면 바로 무효가 된다.
"""

import base64
import hashlib
import hmac
import re
import secrets

# scrypt 설정 (OWASP 권장 최소값 N=2^17은 메모리를 128MB 쓰므로, 작은 서버를 위해 2^15 사용)
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_MAXMEM = 64 * 1024 * 1024

PASSWORD_MIN = 8
RESET_CODE_DIGITS = 6
PASSWORD_MAX = 128
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_valid_email(email: str) -> bool:
    return len(email) <= 254 and EMAIL_RE.match(email) is not None


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, maxmem=SCRYPT_MAXMEM
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, digest = stored.split("$")
        if algo != "scrypt":
            return False
        expected = _unb64(digest)
        actual = hashlib.scrypt(
            password.encode(),
            salt=_unb64(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            maxmem=SCRYPT_MAXMEM,
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_reset_code() -> str:
    """비밀번호 재설정용 6자리 숫자 코드"""
    return f"{secrets.randbelow(10**RESET_CODE_DIGITS):0{RESET_CODE_DIGITS}d}"


def reset_code_hash(user_id: str, code: str) -> str:
    """코드는 해시만 저장한다 (사용자 id를 섞어 같은 코드라도 해시가 다르게)"""
    return hashlib.sha256(f"{user_id}:{code}".encode()).hexdigest()
