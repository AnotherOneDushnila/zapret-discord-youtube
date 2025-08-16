import time, logging
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import WebDriverException
from typing import List, Any, Optional, Dict
from service import Service


service = Service("domains")
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


def get_response(browser: str) -> List[str]:
    browser_options = Options()
    all_domains = []
    config = setup_browser(browser)
    
    if not config:
        return []


    driver_class = config["driver"]
    args = config["args"]


    for arg in args:
        browser_options.add_argument(arg)


    user_agent = get_user_agent("https://www.iana.org")
    if user_agent:
        browser_options.add_argument(f"user-agent={user_agent}")


    HOSTS = input("Enter the host(s), separated by space (without protocol): ").split()


    driver = driver_class(options=browser_options)

    try:
        for host in HOSTS:
            url = f"https://{host}"
            try:
                logging.info(f"\nVisiting {url}...")
                driver.get(url)

                WebDriverWait(driver, 10).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )

                time.sleep(15)  

                domains = driver.execute_script("""
                    const resources = performance.getEntriesByType('resource');
                    const domainSet = new Set(
                        resources.map(r => {
                            try { return (new URL(r.name)).hostname; } 
                            catch (e) { return null; }
                        }).filter(Boolean)
                    );
                    return Array.from(domainSet);
                """)

                logging.info(f"Found domains on {host}: {domains}")
                all_domains.extend(domains)

            except WebDriverException as e:
                logging.exception(f"Failed to load {url}: {e}", exc_info=True)

    finally:
        unique_domains = sorted(set(all_domains))
        driver.quit()

    logging.info(f"\nTotal unique domains found: {len(unique_domains)}")
    return unique_domains



def get_hosts(filename) -> List[str]:
    path = service.find_file(filename)

    with open(path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines()]
    
    if len(lines) > 0:
        return lines

    logging.error("Hostlist file is empty! No hosts returned.")
    raise ValueError("File is empty!")


def get_user_agent(url) -> str:
    try:
        response = requests.get(url)
        response.raise_for_status()  
        return response.request.headers['User-Agent']
    except requests.exceptions.RequestException as e:
        logging.exception(f"Request exeption", exc_info=True)
        return None


def setup_browser(browser: str) -> Optional[Dict[str, Any]]:
    browser_configs = {
        "chrome": {
            "driver": webdriver.Chrome,
            "args": open("args/chrome_args.txt", "r", encoding="utf-8").read().splitlines()
        },
        "firefox": {
            "driver": webdriver.Firefox,
            "args": open("args/firefox_args.txt", "r", encoding="utf-8").read().splitlines()
        },
        "edge": {
            "driver": webdriver.Edge,
            "args": open("args/edge_args.txt", "r", encoding="utf-8").read().splitlines()
        },
        "safari": {
            "driver": webdriver.Safari,
            "args": []  # Safari does not use command line args in the same way
        }
    }

    if browser not in browser_configs:
        logging.info(f"Browser '{browser}' not recognized. Please, try again.")
        return None

    config = browser_configs[browser]
    
    return config

    
def r2txt(domains: List[str]) -> None:
    with open("bc-args-list.txt", "w", encoding="utf-8") as f:
        for domain in domains:
            f.write(domain + " ")


def main() -> None:
    args = service.argparse().parse_args()
    domains = get_response(args.browser)
    r2txt(domains)
    logging.info("\nSaved to bc-args-list.txt")
    



if __name__ == "__main__":
    main()