import os
import locale
from time import time, sleep, gmtime, strftime
from typing import Dict, List
from pathlib import Path
from argparse import ArgumentParser

from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.common.by import By


def parse_args():
    parser = ArgumentParser()
    parser.add_argument("--headless", help="Se habilitado o programa irá rodar sem gui", const="store_true", nargs="?")
    parser.add_argument("--sector", help="Setor a ser listado", default="all")
    parser.add_argument(
        "--time-range", help="Intervalo de tempo a ser procurado", default=[2008, 2023], nargs="+", type=int
    )
    parser.add_argument(
        "--data-path",
        help="Localização do diretório onde os links serão armezados",
        default=os.path.join(os.getcwd(), "data"),
    )

    args = parser.parse_args()
    if args.time_range is not None and len(args.time_range) > 2:
        raise ValueError("Para especificar o ano é necessário apenas informar 1 ano ou o intervalo eg. 2008,2023")
    return args


def scroll_shim(passed_in_driver, object):
    x = object.location["x"]
    y = object.location["y"]
    scroll_by_coord = "window.scrollTo(%s,%s);" % (x, y)
    scroll_nav_out_of_way = "window.scrollBy(0, -120);"
    passed_in_driver.execute_script(scroll_by_coord)
    passed_in_driver.execute_script(scroll_nav_out_of_way)


def clickButton(driver):
    """
    Try n times to click button
    Args:
        driver
    """
    NUM_TRIES = 1
    clicked = False
    for i in range(NUM_TRIES):
        try:
            more = driver.find_element(by=By.ID, value="infinite-handle")
            btn = more.find_element(by=By.TAG_NAME, value="button")
            # Expand news
            if btn.is_displayed():
                try:
                    btn.click()
                    clicked = True
                    break
                except Exception:
                    pass
        except Exception:
            pass

    return clicked


def displayAllNews(driver):
    start_time = 0
    start_function = time()
    end_time = 0
    inner_count = 0

    convert_time = lambda x: strftime("%H:%M:%S", gmtime(x))  # noqa E731
    while inner_count < 100:  # end_time-start_time < 1200:
        print(convert_time(end_time - start_time))
        start_time = time()
        # Try to get the list
        while True:
            try:
                element_news_list = driver.find_element(by=By.ID, value="infinite-list")
                break
            except Exception:
                pass

        # While cant click the button try to scroll over page
        inner_count = 0
        while not clickButton(driver) and inner_count < 100:
            news_list = element_news_list.find_elements(by=By.XPATH, value="//*[starts-with(@id, 'post')]")
            news = news_list[-1]
            scroll_shim(driver, news)

            inner_count += 1
            sleep(1)

        if inner_count > 0:
            author_div = news.find_element(by=By.CLASS_NAME, value="author")
            if "author blog-image" in author_div.get_attribute("class"):
                date_str = author_div.text
                year = date_str.split(",")[0].split(" ")[-1]
            else:
                date_str = author_div.find_elements(by=By.TAG_NAME, value="span")[-1].text
                result = date_str.split(",")
                # There are two possibilities for date_str
                # `Atualizado em 31 dez 2022, 18h04 - Publicado em 31 dez 2022, 18h00 ` or
                # `31 dez 2022, 16h52 `
                result = result[0] if len(result) == 2 else result[1]
                year = result.split(" ")[-1]

            print(f"At year: {year}", end=" | ")

        end_time = time()

    print(f"Last loop: {convert_time(end_time-start_time)}")
    print(f"- Time to display: {convert_time(time()-start_function)}")


def divide_links_by_year(driver, news_list) -> Dict[int, List[str]]:
    # Iterate over each news and save it
    with tqdm(total=len(news_list), desc="Links: ", unit="l") as pb:
        links_by_year = {}
        for n in news_list:
            link = n.find_element(by=By.TAG_NAME, value="a").get_attribute("href")
            # Get year
            author_div = n.find_element(by=By.CLASS_NAME, value="author")
            if "author blog-image" in author_div.get_attribute("class"):
                date_str = author_div.text
                year = date_str.split(",")[0].split(" ")[-1]
            else:
                date_str = author_div.find_elements(by=By.TAG_NAME, value="span")[-1].text
                result = date_str.split(",")
                # There are two possibilities for date_str
                # `Atualizado em 31 dez 2022, 18h04 - Publicado em 31 dez 2022, 18h00 ` or
                # `31 dez 2022, 16h52 `
                result = result[0] if len(result) == 2 else result[1]
                year = result.split(" ")[-1]

            # Add link
            if year in links_by_year.keys():
                links_by_year[year].append(link)
            else:
                # Initialize list
                links_by_year[year] = [link]
            pb.update()

    return links_by_year


def define_time_range(args):
    if len(args.time_range) > 1:
        start = args.time_range[0]
        end = args.time_range[1]
        years = list(range(start, end + 1))
        years_str = f"[{start}, {end}]"  # Just for log
    else:
        years = args.time_range
        years_str = years[0]

    return years, years_str


def main():
    locale.setlocale(locale.LC_ALL, "pt_BR.utf8")  # Set locale to brasil

    # ---
    # Define the time range which will be the search, and the sector
    # ---
    args = parse_args()

    sector = args.sector

    data_path = Path(args.data_path)

    # Start session
    options = webdriver.FirefoxOptions()

    if args.headless:
        options.add_argument("--headless")
        # Define Xsession enviroment variable to run without gui
        # https://stackoverflow.com/a/63305832/14045774
        os.environ["MOZ_HEADLESS"] = "1"

    driver = webdriver.Firefox(options=options)

    # extension_url_path "https://addons.mozilla.org/firefox/downloads/file/4141256/ublock_origin-1.51.0.xpi"

    ext_path = "../ext/ublock_origin-1.51.0.xpi"
    driver.install_addon(ext_path, temporary=True)

    print("Começando a coleta dos links de notícias")
    print(f"Setor: {sector} ")
    if sector == "all":
        search_space, years_str = define_time_range(args)
        print(f"Intervalo de tempo: {years_str}")
    else:
        search_space = [sector]
    print("---")

    for element in search_space:
        driver.get(f"https://veja.abril.com.br/{element}/")
        print(("Year: " if sector == "all" else "Sector: ") + f"{element}")
        # driver.execute_script("document.body.style.zoom='50%'")
        driver.execute_script("document.body.style.MozTransform='scale(0.3  )';")

        # Scroll down the page to show all news
        displayAllNews(driver)

        print("Scroll down is done!!!")
        # List all news
        element_news_list = driver.find_element(by=By.ID, value="infinite-list")
        news_list = element_news_list.find_elements(by=By.XPATH, value="//*[starts-with(@id, 'post')]")

        LINKS_PATH = data_path / sector / "links"
        # Create directory where it will be stored
        os.makedirs(LINKS_PATH, exist_ok=True)

        links = divide_links_by_year(driver, news_list)

        driver.quit()
        # Save links
        print("Saving links")
        for key, links in links.items():
            news_path = LINKS_PATH / (str(key) + ".txt")
            with open(news_path, "w") as f:
                f.write("\n".join(links))
            print(f"Arquivo com links salvo em {news_path}")


if __name__ == "__main__":
    main()
