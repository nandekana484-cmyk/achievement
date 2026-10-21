"""管理者のパスワードのハッシュ(標準ライブラリの hashlib.scrypt)。平文やそのままの値は保存しない。詳細: docs/design/admin.md"""

from __future__ import annotations

import hashlib
import hmac
import secrets

MIN_LENGTH = 8
MAX_LENGTH = 256  # 長すぎる入力でハッシュの計算に時間をかけさせないため

# scrypt の強さ(n=2^14, r=8 で約16MBのメモリ)。変えても、保存した値に含めてあるので古いハッシュも確かめられる
_N, _R, _P = 2**14, 8, 1
_DKLEN = 32


def check_new_password(password: str) -> str | None:
    """新しいパスワードとして使えなければ、理由の文を返す。"""
    if len(password) < MIN_LENGTH:
        return f"パスワードは{MIN_LENGTH}文字以上にしてください"
    if len(password) > MAX_LENGTH:
        return f"パスワードは{MAX_LENGTH}文字以内にしてください"
    try:
        password.encode("utf-8")
    except UnicodeEncodeError:
        return "パスワードに使えない文字が含まれています"
    return None


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=_DKLEN, maxmem=64 * 1024 * 1024)


def hash_password(password: str) -> str:
    """「scrypt$n$r$p$<ソルト>$<ハッシュ>」の形にする。ソルトは管理者ごとに secrets で作る。"""
    salt = secrets.token_bytes(16)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${_scrypt(password, salt, _N, _R, _P).hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        kind, n, r, p, salt, digest = stored.split("$")
        if kind != "scrypt" or len(password) > MAX_LENGTH:
            return False
        actual = _scrypt(password, bytes.fromhex(salt), int(n), int(r), int(p))
    except ValueError:  # 保存した値の形の誤りと、UTF-8 にできない文字(UnicodeEncodeError)
        return False
    return hmac.compare_digest(actual, bytes.fromhex(digest))


# 作業者IDが無いときも同じだけ時間をかけ、IDがあるかどうかを時間で分からないようにするためのハッシュ
DUMMY_HASH = hash_password(secrets.token_hex(16))
