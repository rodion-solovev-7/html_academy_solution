from getpass import getpass
from multiprocessing import cpu_count
from multiprocessing.pool import Pool
from os import environ

import selenium.webdriver.support.expected_conditions as EC
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.options import Options as ChromeOptions

# global
login = None
password = None


def init_driver():
    try:
        options = FirefoxOptions()
        options.headless = True
        driver = webdriver.Firefox(options=options)
        return driver
    except Exception:
        pass

    try:
        options = ChromeOptions()
        options.add_argument("--headless")
        driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
        return driver
    except Exception:
        pass

    # etc

    raise Exception("Поддерживаемый браузер не найден")


def set_text(driver, input_form_id, value):
    input_elem = driver.find_element_by_id(input_form_id)
    input_elem.click()
    input_elem.clear()
    input_elem.send_keys(value)


def sign_in(driver, login, password):
    driver.get("https://htmlacademy.ru/login")
    set_text(driver, "login-email", login)
    set_text(driver, "login-password", password)
    submit = driver.find_element_by_css_selector(".button--full-width[type='submit']")
    submit.click()


def get_tasks_count(driver, trainer_url):
    driver.get(trainer_url)

    waiter10 = WebDriverWait(driver, 10)
    locator = (By.CSS_SELECTOR, ".course-nav__stat")

    try:
        count_elem = waiter10.until(EC.visibility_of_element_located(locator))
    except TimeoutException:
        raise Exception(f"Невозможно определить кол-во заданий")

    parts = count_elem.text.split('/')
    return int(parts[1])


def solve_task(driver, task_url):
    driver.get(task_url)

    if any(driver.find_elements_by_css_selector(".course-challenge-controls__button")):
        raise Exception("Испытания не поддерживаются")

    if not any(driver.find_elements_by_css_selector(".course-layout__sidebar")):
        raise Exception("Конспекты не поддерживаются")

    waiter15 = WebDriverWait(driver, 15)
    waiter40 = WebDriverWait(driver, 40)

    locator = ("UNDEFINED", "UNDEFINED")

    try:
        locator = (By.CSS_SELECTOR, ".course-theory__close.icon-close")
        close = waiter15.until(EC.visibility_of_element_located(locator))
        close.click()

        locator = (By.CSS_SELECTOR, ".course-editor-controls__item--answer")
        show_answer = waiter15.until(EC.visibility_of_element_located(locator))
        # warning: костыль против "element is not clickable because another element obscures it"
        driver.execute_script("arguments[0].click();", show_answer)

        waiter40.until(EC.text_to_be_present_in_element(locator, "Показать ответ"))
    except TimeoutException:
        raise Exception(f"Время ожидания элемента '{locator[1]}' вышло")


def get_trainer_links_id(driver):
    print("Собираю ссылки на все тренажёры...")
    driver.get("https://htmlacademy.ru/courses")

    courses_links = (a.get_attribute("href") for a in driver.find_elements_by_tag_name("a"))
    courses_links = (course_link for course_link in courses_links if course_link.find("courses/") != -1)
    courses_links = set(courses_links)

    trainers_links = []
    for course_link in courses_links:
        driver.get(course_link)

        page_links = (a.get_attribute("href") for a in driver.find_elements_by_tag_name("a"))
        page_links = (page_link for page_link in page_links if page_link.find("continue/course/") != -1)

        trainers_links.extend(page_links)

    links_id = (int(link[link.rfind('/') + 1:]) for link in trainers_links)

    print("Будто бы всё собрал...")
    return sorted(set(links_id))


def collect_task_urls_from_trainers(driver, trainer_urls):
    for trainer_url in trainer_urls:
        try:
            tasks_count = get_tasks_count(driver, trainer_url)
        except Exception as e:
            print(f"Произошла ошибка при поиске кол-ва заданий ({trainer_url}): {e}")
            continue

        trainer_url = driver.current_url
        trainer_url = trainer_url[:trainer_url.rfind('/')]

        yield from (f"{trainer_url}/{i}" for i in range(1, tasks_count + 1))


def solve_tasks_by_urls(driver, task_urls):
    for task_url in task_urls:
        try:
            solve_task(driver, task_url)
        except Exception as e:
            print(f"Произошла ошибка при решении ({task_url}): {e}")
            # unsolved_tasks_urls.append(task_url)


def ptask_collect_tasks(links_id):
    with init_driver() as driver:
        sign_in(driver, login, password)
        return list(collect_task_urls_from_trainers(driver, links_id))


def ptask_solve_tasks(task_urls):
    with init_driver() as driver:
        sign_in(driver, login, password)

        solve_tasks_by_urls(driver, task_urls)


def split_tasks(tasks, workers_count):
    return (tasks[i::workers_count] for i in range(workers_count))


def main():
    global login, password
    login = environ.get("LOGIN", None)
    password = environ.get("PASSWORD", None)

    if login is None:
        login = input("Введите логин HTML Academy: ")
    if password is None:
        password = getpass("Введите пароль HTML Academy: ")

    links_id = [
        39, 42, 44, 45, 46, 50, 51, 53, 55, 57, 58, 65, 66, 70, 71, 73, 74, 76, 79, 80,
        84, 85, 86, 88, 96, 97, 98, 102, 103, 104, 113, 125, 128, 129, 130, 156, 157, 158,
        # 165,
        187, 195, 197, 199, 207, 209, 211, 213, 215, 217, 219, 259, 269, 273, 297, 299,
        301, 303, 305, 307, 309, 337, 339, 341, 343,
        # 345,
        347, 349, 351, 353, 355, 357, 359, 365, 367,
    ]

    links = [f'{"https://htmlacademy.ru/continue/course"}/{link_id}' for link_id in links_id]

    process_count = cpu_count()

    with Pool(process_count) as pool:
        chunked_links = split_tasks(links, process_count)
        results = pool.map(ptask_collect_tasks, chunked_links)

        task_urls = []
        for result in results:
            task_urls.extend(result)

        print("Ссылки собраны")

        chunked_task_urls = split_tasks(task_urls, process_count)
        pool.map(ptask_solve_tasks, chunked_task_urls)

    # print("\nНерешённые задания:", *unsolved_tasks_urls, sep='\n')


if __name__ == "__main__":
    main()
