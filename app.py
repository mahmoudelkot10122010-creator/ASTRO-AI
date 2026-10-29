import flet as ft


def main(page: ft.Page):
    page.title = "ASTRO TEST"
    page.bgcolor = "#F4F5F3"
    page.add(
        ft.Text(
            "ASTRO is working!",
            size=25,
            color="#397A63",
        )
    )


if __name__ == "__main__":
    ft.app(target=main)
