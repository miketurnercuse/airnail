from helium import start_chrome
from time import sleep
from datetime import date, timedelta
import os
import time


PBP_PAGES_DIR = "pbp_pages"


def get_one_day_games(division, year, month, day, page_source_path=PBP_PAGES_DIR):
    month = str(month).zfill(2)
    day = str(day).zfill(2)

    base_url = (
        f"https://www.ncaa.com/scoreboard/lacrosse-women/{division}"
        f"/{year}/{month}/{day}/all-conf"
    )

    driver = start_chrome(base_url, headless=True)
    time.sleep(1)

    try:
        agree_btn = driver.find_element("id", "ncaa-legal-agree")
        agree_btn.click()
        time.sleep(3)
    except Exception:
        pass

    games = driver.find_elements("css selector", "div.gamePod.status-final")

    if not games:
        print(f"No games on {year}-{month}-{day}")
        driver.quit()
        return

    game_pks = []
    for game in games:
        href = game.find_element("css selector", "a.gamePod-link").get_attribute("href")
        pk = int(href.rstrip("/").split("/")[-1])
        game_pks.append(pk)

    os.makedirs(page_source_path, exist_ok=True)

    for pk in game_pks:
        dest = os.path.join(page_source_path, f"{pk}_page.html")
        if os.path.exists(dest):
            continue

        driver.get(f"https://www.ncaa.com/game/{pk}/play-by-play")
        time.sleep(5)

        with open(dest, "w", encoding="utf-8") as f:
            f.write(driver.page_source)

        print(f"Saved {dest}")

    driver.quit()


def scrape_date_range(division, start_year, end_year, page_source_path=PBP_PAGES_DIR):
    for year in range(start_year, end_year + 1):
        current = date(year, 1, 1)
        end = date(year, 12, 31)

        while current <= end:
            get_one_day_games(
                division,
                current.year,
                current.month,
                current.day,
                page_source_path,
            )
            current += timedelta(days=1)


if __name__ == "__main__":
    scrape_date_range(division="d1", start_year=2025, end_year=2025)
