from pandas import DataFrame, concat
from scrapers import Searcher, LegislatorScraper, CandidateScraper, ElectionsScraper, get_driver

class CandidateResearcher:
    def __init__(self):
        self.result = []
        self.basic = DataFrame()
        self.full = DataFrame()
        self.driver = get_driver()

    def research(self, candidate_name):
        try:
            self.scrape_candidate_data(candidate_name)
            self.create_df()
        except Exception as exc:
            print(candidate_name, str(exc))

    def scrape_candidate_data(self, candidate_name):
        search = Searcher(candidate_name)
        cand = CandidateScraper(search.candidate_page_link)
        elec = ElectionsScraper(search.elections_page_link, cand.vpap_candidate_num, self.driver)
        legis = LegislatorScraper(search.legislator_page_link)

        self.temp_result = search.result.copy()
        self.temp_result.update(cand.__dict__)
        self.temp_result.update(elec.result)
        self.temp_result.update(legis.bio)

        self.result.append(self.temp_result)

    def create_df(self):
        self.temp_df = DataFrame([self.temp_result])
        self.basic = concat((self.basic, self.temp_df), sort=False)

        for year in (2019, 2017):
            try:
                self._determine_candidate_party_in_each_year_and_drop_if_candidate_did_not_run(year)
            except KeyError:
                pass

            try:
                self._determine_if_candidate_is_winner(year)
            except KeyError:
                pass

        self.full = concat((self.full, self.temp_df), sort=False)

    def _determine_candidate_party_in_each_year_and_drop_if_candidate_did_not_run(self, year):
        if self.temp_df.loc[0, 'candidate_yoda_name'] == self.temp_df.loc[0, f'{year}_name_D']:
            self.temp_df[f'{year}_candidate_party'] = ['D']
        elif self.temp_df.loc[0, 'candidate_yoda_name'] == self.temp_df.loc[0, f'{year}_name_R']:
            self.temp_df[f'{year}_candidate_party'] = ['R']
        else:
            self.temp_df = self.temp_df.drop(columns=[col for col in self.temp_df.columns if f'{year}' in col])

    def _determine_if_candidate_is_winner(self, year):
        candidate_party = self.temp_df.loc[0, f'{year}_candidate_party']
        winner = self.temp_df.loc[0, f'{year}_winner_{candidate_party}']
        self.temp_df[f'{year}_candidate_is_winner'] = [winner]


def main():
    candidate_list = set(i.strip() for i in open('candidate_list.txt').read().strip().split('\n'))

    cr = CandidateResearcher()
    for candidate in candidate_list:
        cr.research(candidate)

    # cr.full_dropped = cr.full.dropna(subset=['search_string'])

    cr.basic.to_csv('basic.csv', index=False)
    cr.full.to_csv('full.csv', index=False)
    # cr.full_dropped.to_csv('full_dropped.csv', index=False)

    cr.driver.quit()


if __name__ == '__main__':
    main()
