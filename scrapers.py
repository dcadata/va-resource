from requests import get
from bs4 import BeautifulSoup
from time import sleep
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import NoSuchElementException

HOMEPAGE = 'https://www.vpap.org'

def safe_int(text):
    text = text.strip()
    try:
        floated = int(text)
    except TypeError:
        floated = text
    return floated

def money_to_float(money_amount):
    if money_amount:
        try:
            money_amount_float = float(money_amount.replace('$', '').replace(',', ''))
        except TypeError:
            money_amount_float = 0
    else:
        money_amount_float = 0
    return money_amount_float

def get_text_from_elem(box):
    try:
        text = box.text
    except AttributeError:
        text = None
    return text

def get_driver():
    options = Options()
    options.headless = True
    driver = webdriver.Firefox(options=options, executable_path='G:/GitHub/geckodriver.exe')
    return driver


class Requestor:
    def __init__(self, url, params=None):
        r = get(url, params=params, timeout=20)
        sleep(2)
        self.soup = BeautifulSoup(r.text, 'lxml')
        if not r.ok or not self.soup:
            raise AssertionError('Bad request and/or bad Soup')

class Searcher(Requestor):
    def __init__(self, candidate_name):
        self.search_string = candidate_name.strip()
        self.homepage = HOMEPAGE
        self.candidate_page_link = ''
        self.candidate_page_name = None
        super().__init__(url=self.homepage + '/search/', params={'q': self.search_string.lower()})
        self._search()

    def _search(self):
        self._get_candidate_panel_heading()
        self._get_candidate_record_count()
        self._get_candidate_page_link_and_name()
        self._get_elections_page_link()
        self._get_legislator_page_link()
        self.result = {
            'search_string': self.search_string,
            'candidate_yoda_name': self.candidate_page_name,
            'candidate_page_link': self.candidate_page_link,
            'elections_page_link': self.elections_page_link,
            'legislator_page_link': self.legislator_page_link,
        }
        del self.search_string, self.homepage, self.soup, self.candidates_panel_heading, self.candidates_record_count

    def _get_candidate_panel_heading(self):
        self.candidates_panel_heading = self.soup.find('div', class_='panel-heading candidates')
        if not self.candidates_panel_heading:
            raise AssertionError(f'No candidates found for search string "{self.search_string}".')

    def _get_candidate_record_count(self):
        self.candidates_record_count = self.candidates_panel_heading.find('span', class_='badge')

        try:
            self.candidates_record_count = self.candidates_record_count.text
            self.candidates_record_count = int(self.candidates_record_count)
        except (ValueError, AttributeError):
            self.candidates_record_count = 2

        if self.candidates_record_count > 1:
            raise AssertionError(
                f'{self.candidates_record_count} candidates found for search string "{self.search_string}". '
                f'Please disambiguate.'
            )

    def _get_candidate_page_link_and_name(self):
        candidate_page_box = self.soup.find(
            'a', class_='list-group-item', attrs={'href': lambda x: '/candidates/' in str(x)}
        )
        if candidate_page_box:
            candidate_page_rellink = candidate_page_box.get('href', None)
            self.candidate_page_link = self.homepage + candidate_page_rellink
            self.candidate_page_name = candidate_page_box.find('span', class_='linklike').text
        else:
            raise AssertionError(f'No candidate pages found for search query "{self.search_string}".')

    def _get_elections_page_link(self):
        if self.candidate_page_link.endswith('/'):
            self.elections_page_link = self.candidate_page_link + 'elections/'
        else:
            self.elections_page_link = self.candidate_page_link + '/elections/'

    def _get_legislator_page_link(self):
        self.legislator_page_link = self.candidate_page_link.replace('candidates', 'legislators')

class LegislatorScraper(Requestor):
    def __init__(self, legislator_page_link):
        self.bio = {}
        try:
            super().__init__(url=legislator_page_link)
            self._scrape()
        except AssertionError:
            pass  # candidate was never a legislator

    def _scrape(self):
        self._get_bio_overview()
        try:
            self._adjust_bio_length_of_service()
        except KeyError:
            self.bio.update({
                'bio_member_since': None,
                'bio_years_of_service': None,
            })

        del self.soup

    def _get_bio_overview(self):
        panel = self.soup.find('div', class_='panel-group').find('div', class_='panel-body').find(
            'div', class_='panel-body')

        if panel:
            bio_attributes = panel.find_all('p')
            for attr in bio_attributes:
                bio_attribute_name = get_text_from_elem(attr.find('span', class_='small_upper'))
                bio_attribute_name_adjusted = (
                    'bio_' + bio_attribute_name[:-1].strip().lower()
                    .replace(' ', '_').replace('/', '').replace('__', '_')
                )
                bio_attribute_value = get_text_from_elem(attr.find('strong'))
                self.bio.update({bio_attribute_name_adjusted: bio_attribute_value})

    def _adjust_bio_length_of_service(self):
        bio_member_since, bio_years_of_service = self.bio['bio_length_of_service'].split(';', 1)
        bio_member_since = bio_member_since.replace('Member since ', '')
        bio_years_of_service = bio_years_of_service.replace(' years of service', '')
        self.bio.update({
            'bio_member_since': safe_int(bio_member_since),
            'bio_years_of_service': safe_int(bio_years_of_service),
        })
        del self.bio['bio_length_of_service']

class CandidateScraper(Requestor):
    def __init__(self, candidate_page_link):
        self.candidate_page_link = candidate_page_link
        self.vpap_candidate_num = None
        self.name = None
        self.summary = None
        super().__init__(url=self.candidate_page_link)
        self._scrape()

    def _scrape(self):
        self.vpap_candidate_num = self.candidate_page_link.split('/candidates/', 1)[1].split('/', 1)[0]
        self.summary_box = self.soup.find('div', {'style': 'float:left;'})
        self._get_name()
        self._get_summary_data()
        del self.candidate_page_link, self.soup, self.summary_box, self.summary_para_box

    def _get_name(self):
        name_box = self.summary_box.find('h3', {'style': 'margin-top:0;'})
        if name_box:
            self.name = name_box.text

    def _get_summary_data(self):
        self.summary_para_box = self.summary_box.find('p')
        if self.summary_para_box:
            self.summary = self.summary_para_box.text
            self.summary = self.summary.strip().split('\n')[0].strip()

    def _get_chamber_from_summary(self):
        """
        Deliberately unused
        """
        if self.summary and not self.chamber:
            if (
                    'house' in self.summary.lower() or 'assembly' in self.summary.lower()
                    or 'delegate' in self.summary.lower()
            ):
                self.chamber = 'lower'
            elif 'senate' in self.summary.lower():
                self.chamber = 'upper'

    def _get_party_from_summary(self):
        """
        Deliberately unused
        """
        party_box = self.summary_para_box.find('strong')
        if party_box:
            self.party = party_box.text[0]

class ElectionsScraper(Requestor):
    def __init__(self, elections_page_link, vpap_candidate_num, driver):
        self.vpap_candidate_num = vpap_candidate_num
        self.driver = driver
        self.result = {}
        super().__init__(url=elections_page_link)
        self._scrape()

    def _scrape(self):
        self._get_election_data_boxes_and_tables()
        for election_data_box, table in self.election_data_boxes_and_tables:
            self._extract_data_from_election_data_box_and_table(election_data_box, table)

        del self.soup, self.election_data_boxes_and_tables

    def _get_election_data_boxes_and_tables(self):
        money_data_box = self.soup.find('div', class_='col-12 col-lg-9')
        election_data_boxes = money_data_box.find_all('h4')[:4]
        tables = money_data_box.find_all('table', class_='table')[:4]
        self.election_data_boxes_and_tables = zip(election_data_boxes, tables)

    def _extract_data_from_election_data_box_and_table(self, election_data_box, table):
        election_data_link_box = election_data_box.find('a')
        election_name = election_data_link_box.text
        year = election_name.split(' ', 1)[0]

        if year in {'2017', '2019'} and 'general' in election_name.lower():
            if 'house' in election_name or 'assembly' in election_name:
                chamber = 'upper'
            elif 'senate' in election_name:
                chamber = 'lower'
            else:
                chamber = 'other'

            election_link = HOMEPAGE + election_data_link_box.get('href', None)
            self.result.update({
                f'{year}_{chamber}_election_name': election_name,
                f'{year}_{chamber}_election_link': election_link,
            })

            ies = IEScraper(self.driver, self.vpap_candidate_num, election_link)
            ies_result = {
                f'{year}_{chamber}_ie_support': ies.support_amount,
                f'{year}_{chamber}_ie_oppose': ies.oppose_amount,
            }
            self.result.update(ies_result)

            candidate_rows = table.find('tbody').find_all('tr')
            for candidate_row in candidate_rows:
                candidate_data = ElectionsCandidateRowScraper(candidate_row).__dict__
                if candidate_data["party"] in {'D', 'R'}:
                    candidate_data_rekeyed = {}
                    for key, value in candidate_data.items():
                        candidate_data_rekeyed.update({f'{year}_{chamber}_{key}_{candidate_data["party"]}': value})
                        self.result.update(candidate_data_rekeyed)

class ElectionsCandidateRowScraper:
    def __init__(self, candidate_row):
        self.candidate_row = candidate_row
        self.name = None
        self.winner = None
        self.party = None
        self.incumbency = None
        self.money_raised_text = None
        self.money_raised = None
        self._scrape()

    def _scrape(self):
        self._get_elements()
        if self.candidate_data_cell and self.money_cell:
            self._get_result()
            self._get_incumbency_and_party()
            self._get_money_raised()
            del self.money_link_box

        del self.candidate_row, self.candidate_data_cell, self.money_cell

    def _get_elements(self):
        candidate_row_split = self.candidate_row.find_all('td')
        if len(candidate_row_split) == 2:
            self.candidate_data_cell, self.money_cell = self.candidate_row.find_all('td')
            self.money_link_box = self.money_cell.find('a', {'href': lambda x: '/finance_summary/' in str(x)})
        else:
            self.candidate_data_cell, self.money_cell = None, None

    def _get_result(self):
        self.name = self.candidate_data_cell.find('a').text
        self.winner = bool(self.candidate_data_cell.find('span', class_='badge'))

    def _get_incumbency_and_party(self):
        incumbency_and_party = self.candidate_data_cell.text.replace(self.name, '').replace('Winner', '').strip()
        self.incumbency, self.party = incumbency_and_party.split('(', 1)
        self.incumbency = self.incumbency.strip() == '*'
        self.party = self.party.strip().replace(')', '')

    def _get_money_raised(self):
        if self.money_link_box:
            self.money_raised_text = self.money_link_box.text
            self.money_raised = money_to_float(self.money_raised_text)

class IEScraper:
    def __init__(self, driver, vpap_candidate_num, election_link):
        self.driver = driver
        self.vpap_candidate_num = vpap_candidate_num
        self.election_link = election_link
        self.barlinks = []
        self.support_amount_text = None
        self.support_amount = None
        self.oppose_amount_text = None
        self.oppose_amount = None
        self._get()

    def _get(self):
        self._get_ie_details_elem()
        if self.details_elem:
            self._get_svg_elem()
            self._get_barlinks()
            self._get_amounts()
            del self.details_elem, self.barlink_elems, self.barlinks
        self._adjust_null_amounts_to_zero()
        del self.vpap_candidate_num, self.election_link, self.driver

    def _get_ie_details_elem(self):
        self.driver.get(self.election_link)
        try:
            self.details_elem = self.driver.find_element_by_id('ie_details')
        except NoSuchElementException:
            self.details_elem = None

    def _get_svg_elem(self):
        chart_elem = self.details_elem.find_element_by_id('svgchart')
        svg_elem = chart_elem.find_element_by_tag_name('svg')
        self.barlink_elems = svg_elem.find_elements_by_class_name('barlink')

    def _get_barlinks(self):
        for barlink_elem in self.barlink_elems:
            barlink_href = barlink_elem.get_attribute('href')

            if barlink_href:
                barlink_href_value = barlink_href.get('animVal', None)

                if barlink_href_value:
                    barlink = barlink_href_value
                else:
                    barlink = barlink_href.get('baseVal', None)

            else:
                barlink = ''

            self.barlinks.append((barlink, barlink_elem))

    def _get_amounts(self):
        for barlink, barlink_elem in self.barlinks:
            if f'candidate={self.vpap_candidate_num}' in barlink:

                for position in ('support', 'oppose'):
                    if f'position={position}' in barlink:
                        g_elem = barlink_elem.find_element_by_class_name('g_rect')
                        text_elem = g_elem.find_element_by_class_name('amount')

                        text_amount = text_elem.text
                        amount = money_to_float(text_amount)
                        self.__dict__.update({
                            f'{position}_amount_text': text_amount,
                            f'{position}_amount': amount,
                        })

    def _adjust_null_amounts_to_zero(self):
        if not self.support_amount_text:
            self.support_amount_text = 0
        if not self.support_amount:
            self.support_amount = 0
        if not self.oppose_amount_text:
            self.oppose_amount_text = 0
        if not self.oppose_amount:
            self.oppose_amount = 0
