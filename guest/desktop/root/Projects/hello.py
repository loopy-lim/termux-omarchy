"""Loopy Desktop에서 Geany로 바로 수정해 볼 수 있는 예제."""


def greeting(name: str) -> str:
    return f"안녕하세요, {name}!"


if __name__ == "__main__":
    print(greeting("Wayland"))
