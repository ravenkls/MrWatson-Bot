import requests
from bs4 import BeautifulSoup


country = "UK"


cases_page = requests.get(
    "https://www.gov.uk/guidance/coronavirus-covid-19-information-for-the-public"
)
soup = BeautifulSoup(cases_page.text, "html.parser")
summary = soup.find("h2", {"id": "number-of-cases"}).find_next("p")
table_cells = summary.find_next("tbody").find_all("td")
regions = {loc.text: n.text for loc, n in zip(table_cells[0::2], table_cells[1::2])}

risk_level = soup.find("h2", {"id": "risk-level"}).find_next("a")
print(risk_level)


# print(summary.text, regions)
