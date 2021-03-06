from abc import abstractmethod
from requests import get
from bs4 import BeautifulSoup
from time import sleep
from selenium.common.exceptions import NoSuchElementException


HOMEPAGE = 'https://www.vpap.org'


def safe_int(text):
    if text:
        text = text.strip()
        if text == '-' or text == 'None':
            result = 0
        else:
            try:
                result = int(text)
            except ValueError:
                result = text
    else:
        result = 0
    return result

def money_to_float(money_text):
    if money_text:
        try:
            money_amount = float(money_text.replace('$', '').replace(',', ''))
        except ValueError:
            money_amount = 0
    else:
        money_amount = 0
    return money_amount

def pct_to_float(pct_text):
    if pct_text:
        try:
            pct_amount = float(pct_text.replace('%', '').replace(',', '').replace('-', ''))
        except ValueError:
            pct_amount = 0
    else:
        pct_amount = 0
    return pct_amount

def get_text_from_elem(elem, result=None):
    try:
        text = elem.text
    except AttributeError:
        text = result
    return text


class Requester:
    def __init__(self, url, params=None):
        r = get(url, params=params, timeout=20)
        sleep(2)
        self.soup = BeautifulSoup(r.text, 'lxml')
        if not r.ok or not self.soup:
            raise AssertionError('Bad request and/or bad Soup')


class Searcher(Requester):
    def __init__(self, candidate_name):
        self.search_string = candidate_name.strip()
        self.candidate_page_link = ''
        self.candidate_page_name = None
        super().__init__(url=HOMEPAGE + '/search/', params={'q': self.search_string.lower()})
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
        del self.search_string, self.soup, self.candidates_panel_heading, self.candidates_record_count

    def _get_candidate_panel_heading(self):
        self.candidates_panel_heading = self.soup.find('div', class_='panel-heading candidates')
        if not self.candidates_panel_heading:
            raise AssertionError(f'No candidates found for search string "{self.search_string}".')

    def _get_candidate_record_count(self):
        self.candidates_record_count = self.candidates_panel_heading.find('span', class_='badge')
        self.candidates_record_count = safe_int(get_text_from_elem(self.candidates_record_count, '2'))
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
            self.candidate_page_link = HOMEPAGE + candidate_page_box.get('href', '')
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


class LegislatorScraper(Requester):
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
            for attr in panel.find_all('p'):
                bio_attribute_name = get_text_from_elem(attr.find('span', class_='small_upper'))
                if bio_attribute_name:
                    bio_attribute_name_adjusted = ('bio_' + bio_attribute_name[:-1].strip().lower()
                                                   .replace(' ', '_').replace('/', '').replace('__', '_'))
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


class CandidateScraper(Requester):
    def __init__(self, candidate_page_link):
        self.candidate_page_link = candidate_page_link
        self.vpap_candidate_num = None
        self.name = None
        self.summary = None
        self.has_ie = None
        self.as_state_link = None
        self.as_federal_link = None
        super().__init__(url=self.candidate_page_link)
        self._scrape()

    def _scrape(self):
        self.vpap_candidate_num = self.candidate_page_link.split('/candidates/', 1)[1].split('/', 1)[0]
        self.summary_box = self.soup.find('div', {'style': 'float:left;'})
        self._get_name()
        self._get_summary_data()
        self._get_state_and_federal_candidate_links()
        self._get_sidebar_menu()
        self._get_ie_link()
        self._get_current_election_data()
        del self.candidate_page_link, self.soup, self.summary_box, self.summary_para_box, self.sidebar_menu

    def _get_name(self):
        name_box = self.summary_box.find('h3', {'style': 'margin-top:0;'})
        if name_box:
            self.name = name_box.text

    def _get_summary_data(self):
        self.summary_para_box = self.summary_box.find('p')
        if self.summary_para_box:
            self.summary = self.summary_para_box.text
            self.summary = self.summary.strip().split('\n')[0].strip()

    def _get_state_and_federal_candidate_links(self):
        federal_button_elem = self.soup.find(
            'a', class_='btn', attrs={'type': 'button', 'href': lambda x: str(x).startswith('/candidates/federal/')}
        )
        if not federal_button_elem:
            federal_button_elem = self.soup.find(
                'a', class_='btn', attrs={'type': 'button'}, text='As Federal Candidate'
            )

        if federal_button_elem:
            statelocal_button_elem = self.soup.find(
                'a', class_='btn', attrs={'type': 'button'}, text='As State/Local Candidate'
            )
            self.as_federal_link = HOMEPAGE + federal_button_elem.get('href', None)
            self.as_state_link = HOMEPAGE + statelocal_button_elem.get('href', None)

    def _get_sidebar_menu(self):
        self.sidebar_menu = self.soup.find('ul', class_='vsubmenu')
        # if self.sidebar_menu:
        #     self.sidebar_menu_items = self.sidebar_menu.find_all('li')
        # else:
        #     self.sidebar_menu_items = []

    def _get_ie_link(self):
        if self.sidebar_menu:
            self.has_ie = bool(self.sidebar_menu.find('li', text='Independent Expenditures'))

    def _get_current_election_data(self):
        # comment in HTML for this elem: shows the next upcoming election, unless there was an election recently,
        # in which case it displays the results
        show_all_elections_link_elem = self.soup.find('a', text=lambda x: 'Show all elections for' in str(x))
        if show_all_elections_link_elem:
            current_election_elem = show_all_elections_link_elem.find_parent('div', class_='panel-body')
            self.__dict__.update(CandidateCurrentElectionScraper(current_election_elem, self.name).result)


class CandidateCurrentElectionScraper:
    def __init__(self, current_election_elem, candidate_name):
        self.current_election_elem = current_election_elem
        self.candidate_name = candidate_name
        self.candidate_rows = []
        self.result = {}
        self._scrape()
        del self.candidate_rows

    def _scrape(self):
        self._scrape_header()
        self._scrape_table()

    def _scrape_header(self):
        election_office_header_elem = self.current_election_elem.find('h4')
        if election_office_header_elem:
            election_office_rellink_elem = election_office_header_elem.find('a')
            if get_text_from_elem(election_office_rellink_elem):
                office_text = election_office_rellink_elem.text.strip()
                if office_text:
                    self.result.update({
                        'election_office': ' '.join(i.strip() for i in office_text.split('\n')),
                        'election_rellink': election_office_rellink_elem.get('href', None),
                    })
            election_date_elem = election_office_header_elem.find('span', class_='small')
            self.result.update({'election_date': get_text_from_elem(election_date_elem)})

    def _scrape_table(self):
        table = self.current_election_elem.find('table', class_='table')
        if table:
            self.candidate_rows = table.find('tbody').find_all('tr')[:2]
            for candidate_row in self.candidate_rows:
                row_scraper = CurrentElectionCandidateRowScraper(candidate_row)
                if row_scraper.name:
                    last_name = row_scraper.name.split(',', 1)[0]
                    candidate = 'candidate' if last_name.lower() in self.candidate_name.lower() else 'opponent'
                    for key, value in CurrentElectionCandidateRowScraper(candidate_row).__dict__.items():
                        self.result.update({f'{candidate}_{key}': value})


class ElectionsScraper(Requester):
    def __init__(self, elections_page_link, **kwargs):
        self.kwargs = kwargs
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
        election_data_boxes = money_data_box.find_all('h4')[:6]
        tables = money_data_box.find_all('table', class_='table')[:6]
        self.election_data_boxes_and_tables = zip(election_data_boxes, tables)

    def _extract_data_from_election_data_box_and_table(self, election_data_box, table):
        election_data_link_box = election_data_box.find('a')
        election_name = election_data_link_box.text
        year = election_name.split(' ', 1)[0]

        if int(year) >= 2017 and 'general' in election_name.lower():
            if 'house of delegates' in election_name.lower() or 'assembly' in election_name.lower():
                chamber = 'lower'
            elif 'state senate' in election_name.lower():
                chamber = 'upper'
            else:
                chamber = 'other'

            election_link = HOMEPAGE + election_data_link_box.get('href', None)
            self.result.update({
                f'{year}_{chamber}_election_name': election_name,
                f'{year}_{chamber}_election_link': election_link,
            })

            if self.kwargs.get('has_ie', None) and self.kwargs.get('driver', None):
                ies = IEScraper(self.kwargs['driver'], self.kwargs.get('vpap_candidate_num', None), election_link)
                self.result.update({
                    f'{year}_{chamber}_ie_support': ies.support_amount,
                    f'{year}_{chamber}_ie_oppose': ies.oppose_amount,
                })

            candidate_rows = table.find('tbody').find_all('tr')[:2]
            for candidate_row in candidate_rows:
                candidate_data = MoneyRaisedCandidateRowScraper(candidate_row).__dict__
                if candidate_data["party"] in {'D', 'R'}:
                    candidate_data_rekeyed = {}
                    for key, value in candidate_data.items():
                        candidate_data_rekeyed.update({f'{year}_{chamber}_{key}_{candidate_data["party"]}': value})
                        self.result.update(candidate_data_rekeyed)


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


class CandidateRowScraper:
    def __init__(self, candidate_row):
        self.row = candidate_row
        self.candidate_cell = None
        self.remaining_cells = []
        self.name = None
        self.winner = None
        self.party = None
        self.incumbency = None
        self._scrape()

    def _scrape(self):
        self._get_candidate_data_cell()
        self._get_candidate_data()
        self._get_remaining_cells()
        self._get_remaining_cells_data()
        del self.row, self.candidate_cell, self.remaining_cells

    def _get_candidate_data_cell(self):
        cells = self.row.find_all('td')
        if cells:
            self.candidate_cell = cells[0]
            self.remaining_cells = cells[1:]

    def _get_candidate_data(self):
        if self.candidate_cell:
            if self.candidate_cell.text:
                lower_ctext = self.candidate_cell.text.lower()
                if not (
                    'withdrawn candidates' in lower_ctext or 'did not seek' in lower_ctext
                    or 'sought other office' in lower_ctext or 'failed to' in lower_ctext
                ):
                    self.winner = bool(self.candidate_cell.find('span', class_='badge'))
                    candidate_items = [i.strip() for i in self.candidate_cell.text.strip().split('\n')]
                    if len(candidate_items) > 1:
                        self.name, self.party = candidate_items[:2]

                        if self.name.endswith('*'):
                            self.incumbency = True
                            self.name = self.name.replace('*', '').strip()
                        else:
                            self.incumbency = False

                        self.party = self.party.replace('(', '').replace(')', '')

    @abstractmethod
    def _get_remaining_cells(self):
        pass

    @abstractmethod
    def _get_remaining_cells_data(self):
        pass


class MoneyRaisedCandidateRowScraper(CandidateRowScraper):
    def __init__(self, candidate_row):
        self.money_cell = None
        self.money_raised_text = None
        self.money_raised = None
        super().__init__(candidate_row)
        del self.money_cell

    def _get_remaining_cells(self):
        if self.remaining_cells:
            self.money_cell = self.remaining_cells[0]

    def _get_remaining_cells_data(self):
        if self.money_cell:
            money_link_box = self.money_cell.find('a', {'href': lambda x: '/finance_summary/' in str(x)})
            if money_link_box:
                # .get('href', None)
                self.money_raised_text = money_link_box.text
                self.money_raised = money_to_float(self.money_raised_text)


class CurrentElectionCandidateRowScraper(CandidateRowScraper):
    def __init__(self, candidate_row):
        self.spent_elem = None
        self.votes_elem = None
        self.voteshare_elem = None
        self.spent_text = None
        self.votes_text = None
        self.voteshare_text = None
        self.spent = None
        self.votes = None
        self.voteshare = None
        super().__init__(candidate_row)
        del self.spent_elem, self.votes_elem, self.voteshare_elem

    def _get_remaining_cells(self):
        if self.remaining_cells:
            augmented_remaining_cells = (self.remaining_cells + [None, None, None])[:3]
            self.spent_elem, self.votes_elem, self.voteshare_elem = augmented_remaining_cells

    def _get_remaining_cells_data(self):
        self._get_spent()
        self._get_votes()
        self._get_voteshare()

    def _get_spent(self):
        if self.spent_elem:
            spent_rellink_elem = self.spent_elem.find('a', {'href': lambda x: '/finance_summary/' in str(x)})
            self.spent_text = get_text_from_elem(spent_rellink_elem)
            if self.spent_text:
                self.spent = money_to_float(self.spent_text)

    def _get_votes(self):
        if self.votes_elem:
            self.votes_text = get_text_from_elem(self.votes_elem, '0')
            self.votes = safe_int(self.votes_text.replace(',', ''))

    def _get_voteshare(self):
        if self.voteshare_elem:
            self.voteshare_text = get_text_from_elem(self.voteshare_elem, '0')
            self.voteshare = pct_to_float(self.voteshare_text)
