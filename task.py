from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from pandas import DataFrame, concat, read_csv
from scrapers import Searcher, LegislatorScraper, CandidateScraper, ElectionsScraper

def fillna_with_didnotrun(df):
    for col in df.columns:
        if col.startswith('2019') or col.startswith('2017'):
            df[col].fillna(inplace=True, value='N/A')


class CandidateResearcher:
    def __init__(self, driver, candidate_name):
        self.driver = driver
        self.candidate_name = candidate_name
        self.result = {}
        self.basic = DataFrame()
        self.full = DataFrame()
        self._scrape_data()
        self._create_dataframes()

    def _scrape_data(self):
        search = Searcher(self.candidate_name)
        cand = CandidateScraper(search.candidate_page_link)
        elec = ElectionsScraper(search.elections_page_link, cand.vpap_candidate_num, self.driver)
        legis = LegislatorScraper(search.legislator_page_link)

        self.result = search.result.copy()
        self.result.update(cand.__dict__)
        self.result.update(elec.result)
        self.result.update(legis.bio)

    def _create_dataframes(self):
        self.basic = DataFrame([self.result])
        self.full = self.basic.copy()

        for year in (2019, 2017):
            for chamber in ('lower', 'upper', 'other'):
                if [col for col in self.full.columns if chamber in col]:
                    self._add_fields_to_full_dataframe(year, chamber)

    def _add_fields_to_full_dataframe(self, year, chamber):
        self._create_fields_with_default_values(year, chamber)

        candidate_ran = False
        if f'{year}_{chamber}_name_D' in self.full.columns:
            if self.full.loc[0, 'candidate_yoda_name'] == self.full.loc[0, f'{year}_{chamber}_name_D']:
                self._add_fields_based_on_party(year, chamber, 'D')
                candidate_ran = True

        if f'{year}_{chamber}_name_R' in self.full.columns:
            if self.full.loc[0, 'candidate_yoda_name'] == self.full.loc[0, f'{year}_{chamber}_name_R']:
                self._add_fields_based_on_party(year, chamber, 'R')
                candidate_ran = True

        if not candidate_ran:
            self.full = self.full.drop(columns=[col for col in self.full.columns if f'{year}_{chamber}' in col])

    def _create_fields_with_default_values(self, year, chamber):
        self.full[f'{year}_{chamber}_candidate_party'] = [None]
        self.full[f'{year}_{chamber}_is_winner'] = [None]
        self.full[f'{year}_{chamber}_is_incumbent'] = [None]
        self.full[f'{year}_{chamber}_raised'] = [None]

    def _add_fields_based_on_party(self, year, chamber, party_letter):
        party_letter = party_letter.upper()

        self.full[f'{year}_{chamber}_candidate_party'] = [party_letter]

        winner = self.full.loc[0, f'{year}_{chamber}_winner_{party_letter}']
        self.full[f'{year}_{chamber}_is_winner'] = [winner]

        incumbent = self.full.loc[0, f'{year}_{chamber}_incumbency_{party_letter}']
        self.full[f'{year}_{chamber}_is_incumbent'] = [incumbent]

        raised = self.full.loc[0, f'{year}_{chamber}_money_raised_{party_letter}']
        self.full[f'{year}_{chamber}_raised'] = [raised]

class MultiCandidateResearcher:
    def __init__(self):
        self.result = []
        self.errors = []
        self.basic = DataFrame()
        self.full = DataFrame()
        self._get_driver()

    def _get_driver(self):
        options = Options()
        options.headless = True
        self.driver = webdriver.Firefox(options=options, executable_path='G:/GitHub/geckodriver.exe')

    def research(self, candidate_list):
        for candidate in candidate_list:
            try:
                cr = CandidateResearcher(self.driver, candidate)

                self.result.append(cr.result)
                self.basic = concat((self.basic, cr.basic), sort=False)

                self.full = concat((self.full, cr.full), sort=False)
                fillna_with_didnotrun(self.full)

            except Exception as exc:
                print(candidate, str(exc))
                self.errors.append({
                    'candidate': candidate,
                    'error_message': str(exc),
                })

class Exporter:
    def __init__(self):
        self.year = 2019
        self.chamber = 'upper'
        self.candidate_list = set(
            i.strip() for i in open(f'{self.year}_{self.chamber}_candidate_list.txt').read().strip().split('\n')
        )

    def _condense(self, full_all):
        mapper = {}
        for desired_col, curr_col in [line.split(':', 1) for line in open('mapper.txt').read().strip().split('\n')]:
            mapper.update({curr_col.format(year=self.year, chamber=self.chamber): desired_col})

        condensed_all = full_all[list(mapper.keys())].rename(columns=mapper)
        return condensed_all

    def _merge_full_existing_with_full(self, full):
        try:
            full_existing = read_csv(f'data/{self.year}_{self.chamber}_full.csv')
            full_all = concat((full_existing, full), sort=False)
            fillna_with_didnotrun(full_all)
        except FileNotFoundError:
            full_all = full
        return full_all

    def _export_main_dataframes(self, full, full_all, condensed_all):
        full.to_csv(f'{self.year}_{self.chamber}_full_new.csv', index=False)
        full_all.to_csv(f'data/{self.year}_{self.chamber}_full.csv', index=False)
        condensed_all.to_csv(f'data/{self.year}_{self.chamber}_condensed.csv', index=False)

    def _export_contingency_dataframes(self, mcr):
        full_dropped = mcr.full.dropna(subset=['search_string'])
        if len(full_dropped) != len(mcr.full):
            mcr.basic.to_csv(f'{self.year}_{self.chamber}_basic.csv', index=False)
            full_dropped.to_csv(f'{self.year}_{self.chamber}_full_dropped.csv', index=False)

        if mcr.errors:
            errors = DataFrame(mcr.errors)
            errors.to_csv(f'{self.year}_{self.chamber}_errors.csv', index=False)

    def main(self):
        mcr = MultiCandidateResearcher()
        mcr.research(self.candidate_list)

        full_all = self._merge_full_existing_with_full(mcr.full)
        condensed_all = self._condense(full_all)

        self._export_main_dataframes(mcr.full, full_all, condensed_all)
        self._export_contingency_dataframes(mcr)

        mcr.driver.quit()


if __name__ == '__main__':
    ex = Exporter()
    ex.main()
