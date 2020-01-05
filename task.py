from pandas import DataFrame, concat
from scrapers import Searcher, LegislatorScraper, CandidateScraper, ElectionsScraper, get_driver

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
            try:
                self._determine_candidate_party_in_each_year_and_drop_if_candidate_did_not_run(year)
            except KeyError:
                pass

            try:
                self._determine_if_candidate_is_winner(year)
            except KeyError:
                pass

    def _determine_candidate_party_in_each_year_and_drop_if_candidate_did_not_run(self, year):
        if self.full.loc[0, 'candidate_yoda_name'] == self.full.loc[0, f'{year}_name_D']:
            self.full[f'{year}_candidate_party'] = ['D']
        elif self.full.loc[0, 'candidate_yoda_name'] == self.full.loc[0, f'{year}_name_R']:
            self.full[f'{year}_candidate_party'] = ['R']
        else:
            self.full = self.full.drop(columns=[col for col in self.full.columns if f'{year}' in col])

    def _determine_if_candidate_is_winner(self, year):
        candidate_party = self.full.loc[0, f'{year}_candidate_party']
        winner = self.full.loc[0, f'{year}_winner_{candidate_party}']
        self.full[f'{year}_candidate_is_winner'] = [winner]

class MultiCandidateResearcher:
    def __init__(self):
        self.result = []
        self.basic = DataFrame()
        self.full = DataFrame()
        self.driver = get_driver()

    def research(self, candidate_list):
        for candidate in candidate_list:
            try:
                cr = CandidateResearcher(self.driver, candidate)
                self.result.append(cr.result)
                self.basic = concat((self.basic, cr.basic), sort=False)
                self.full = concat((self.full, cr.full), sort=False)
            except Exception as exc:
                print(candidate, str(exc))


def main():
    mcr = MultiCandidateResearcher()

    candidate_list = set(i.strip() for i in open('candidate_list.txt').read().strip().split('\n')[7:10])

    mcr.research(candidate_list)

    full_dropped = mcr.full.dropna(subset=['search_string'])

    mcr.basic.to_csv('basic.csv', index=False)
    mcr.full.to_csv('full.csv', index=False)

    if len(full_dropped) != len(mcr.full):
        full_dropped.to_csv('full_dropped.csv', index=False)

    mcr.driver.quit()


if __name__ == '__main__':
    main()
