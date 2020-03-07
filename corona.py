import requests
from bs4 import BeautifulSoup


country = "UK"


cases_page = requests.get("https://www.worldometers.info/coronavirus/#countries")
soup = BeautifulSoup(cases_page.text, "html.parser")
rows = soup.select_one("tbody").find_all("tr")
country_row = [r for r in rows if r.select_one("td").text.strip() == country]

if country_row:
    (
        country,
        cases,
        new_cases,
        deaths,
        new_deaths,
        active_cases,
        recovered,
        serious_critical,
    ) = [i.text.strip() for i in country_row[0].find_all("td")]

    print(country, cases, new_cases, deaths)
