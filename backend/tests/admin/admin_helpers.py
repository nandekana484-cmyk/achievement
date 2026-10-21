"""管理画面のAPIのテストの補助(定数とログイン)。"""

PASSWORD = "right-pass-1"
H = {"X-Genba-Admin": "1"}


def login(client, worker_id="K0042", password=PASSWORD):
    return client.post("/api/admin/login", json={"worker_id": worker_id, "password": password}, headers=H)
