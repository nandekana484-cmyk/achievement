"""業務ルールの違反などの例外(main.py で 409 / 404 / 503 に変える)。メッセージは画面にそのまま出せる文。"""

from __future__ import annotations


class RuleViolation(Exception):
    """業務ルールに反する操作(409)。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class Busy(Exception):
    """ほかの処理と書き込みが重なり、記録できなかった(503)。同じ request_id で送り直せば記録される。"""

    message = "他の処理と重なったため、記録できませんでした。もう一度押してください"


class NotFound(Exception):
    """対象が見つからない(404)。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
