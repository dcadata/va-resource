from pandas import DataFrame, concat, read_csv
from scrapers import Searcher, LegislatorScraper, CandidateScraper, ElectionsScraper, get_driver

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
                try:
                    if [col for col in self.full.columns if chamber in col]:
                        self._add_fields_to_full_dataframe(year, chamber)
                except KeyError:
                    pass

    def _add_fields_to_full_dataframe(self, year, chamber):
        self._create_fields_with_default_values(year, chamber)

        if self.full.loc[0, 'candidate_yoda_name'] == self.full.loc[0, f'{year}_{chamber}_name_D']:
            self._add_fields_based_on_party(year, chamber, 'D')
        elif self.full.loc[0, 'candidate_yoda_name'] == self.full.loc[0, f'{year}_{chamber}_name_R']:
            self._add_fields_based_on_party(year, chamber, 'R')
        else:
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
                fillna_with_didnotrun(self.full)

            except Exception as exc:
                print(candidate, str(exc))


def main():
    YEAR = 2019
    CHAMBER = 'upper'

    mcr = MultiCandidateResearcher()

    candidate_list = set(i.strip() for i in open(f'{YEAR}_{CHAMBER}_candidate_list.txt').read().strip().split('\n'))

    mcr.research(candidate_list)

    full_existing = read_csv('full.csv')
    full = concat((full_existing, mcr.full), sort=False)
    fillna_with_didnotrun(full)
    full.to_csv('full.csv', index=False)

    mcr.full.to_csv('full_new.csv', index=False)

    sd_mapper = {}
    for sd_col, curr_col in [line.split(':', 1) for line in open('sd_mapper.txt').read().strip().split('\n')]:
        sd_mapper.update({curr_col.format(year=YEAR, chamber=CHAMBER): sd_col})

    sd = mcr.full.loc[:, list(sd_mapper.keys())].rename(columns=sd_mapper)
    sd.to_csv('sd.csv', index=False)

    full_dropped = mcr.full.dropna(subset=['search_string'])
    if len(full_dropped) != len(mcr.full):
        mcr.basic.to_csv('basic.csv', index=False)
        full_dropped.to_csv('full_dropped.csv', index=False)

    mcr.driver.quit()


if __name__ == '__main__':
    main()
