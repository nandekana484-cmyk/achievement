"""業務ルールの違反を表す例外。メッセージは画面にそのまま出せる日本語の文にする。

API(main.py の例外ハンドラ)で、RuleViolation は 409、NotFound は 404、Busy は 503 に変える。
"""

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
