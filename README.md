# VA 2017 and 2019 Major Party Resource Allocation Study

## Data Collection (Scraping) Scripts

These scripts enable you to scrape VPAP. They currently include only functionality that has been requested, but can be extended to add more features.

CSVs are published (in the /data directory) with data for specific requested candidates.

Uses Requests, BeautifulSoup, Selenium, Pandas.

***

## Notes

* `bio_` fields come from the Legislators page Overview section ([example here](https://www.vpap.org/legislators/289576-wendy-gooditis/)), so generally they're only available for candidates who were/are legislators. Candidates who ran and lost do not have `bio_` fields. `bio_` fields are also often missing for candidates who did serve as legislators. However, some fields can be parsed (manually for now) out of the `summary` field.

***

## TO-DO

### Parse out candidate's gender from `summary`

* Per above, `bio_gender` is only available for legislators. For candidates, attempt to parse out gender from `summary` based on the pronouns used for the candidate. This won't be perfect because some candidates do not have summaries and other candidates have summaries but no pronouns are used, e.g. "Jane Doe has served in the House of Delegates since 2017." It may also be possible to guess gender based on first name, but this is not always reliable either.

### Parse out district from election title

* e.g. `2019 House of Delegates - District 10 - Regular General` => `HD-10`

### Additional Fields

* elections page:
  * district name
  * district index (competitiveness rating)
  * date of election
  * candidates' names; parties; incumbency; # of votes; voteshare; winner

* candidate page:
  * campaign website

<!-- ***

### Ballotpedia.org scraper(s) (separate repos)

* Searcher
* Others...

## Completed

### Functionality to scrape Independent Expenditures (IE):

* These are presented in an SVG (a type of format that embeds within an HTML page - [example here](https://www.vpap.org/offices/house-of-delegates-13/elections/?year_and_type=2017regular) - it is the chart) on VPAP. The SVG does not load without Javascript, so it can't be scraped with Requests. If it loaded, it would be easy to scrape the position (pro-/anti-candidate) and the amounts. I'm still researching if it's possible to load SVGs with Requests, but so far, it seems unlikely.

* IEs are also available in text format in another page within VPAP ([example here](https://www.vpap.org/candidates/5663/indexpenditures/spenders/?election=8815&candidate=5663&position=support), under "Total independent expenditures" near the top), but the URL to that other page is only available in the SVG. I'm currently working on trying to recreate the URL of that other page so that I can (programatically) visit it and simply scrape the text. The challenge in recreating the URL comes from the election # (`election=8815` in this case).

* Another option is to use Selenium to load Javascript, thus loading the SVG. This is a less preferred option because it is more time consuming to run; however, there aren't *that* many candidates in total, so it's still very possible to do this if the second option above doesn't work out.

* **Completed successfully using Selenium!**

 -->
