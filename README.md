# Open Library Author Analysis

A Python project that pulls an author's bibliography from the Open Library API,
cleans and deduplicates the data, and produces structured tables and charts
summarizing their publishing history.


## Why this project

Open Library's data is crowdsourced, which means the same book often appears
as multiple separate "work" entries — different contributors, different
punctuation, sometimes genuine duplicates with different edition counts.
This project was built to practice working with a real, messy public API:
pulling data with `requests`, cleaning and deduplicating it, and turning it
into something analyzable with `pandas` and visual with `plotly`.


## What it does

1. Takes an author's name as input and searches Open Library for a matching
   author record, filtering out false matches when multiple authors share
   a name.
2. Pulls every work associated with that author in a single batched request.
3. Normalizes and deduplicates work titles (case, punctuation, and
   formatting differences), keeping the most complete entry for each book
   based on edition count, publish year, and page count.
4. Filters works to those published during the author's known lifetime,
   handling cases where birth or death dates are missing or incomplete.
5. Displays the results as clean, readable tables: general author info,
   the full list of works, and works published during their lifetime.
6. Visualizes the results with interactive charts: books published per year
   during the author's lifetime, the twenty most-republished books by
   edition count, and how a book's edition count has grown over time.



## Report contents

The generated report (`report.html`) always includes, in this order:

- The author's general info and top subjects
- A table of works published during the author's lifetime
- Three charts: books published per year, editions per book, and editions
  over time

**If the author is deceased** (a death date is available), the report also
includes:

- A full table of every work recorded for the author in Open Library,
  shown after the charts

**If the author appears to still be alive, or their death date is missing**:

- Only the lifetime-scoped table is shown, with a note explaining that
  results include everything published, since an upper bound on their
  lifetime couldn't be determined
- The full works table is omitted, since it would be nearly identical to
  the lifetime table



## Tools used

- `requests` — fetching data from the Open Library API
- `re` — title normalization and input validation
- `pandas` — structuring and displaying the cleaned data
- `plotly` — interactive charts (bar charts, scatter plot)



## Data source

[Open Library API](https://openlibrary.org/developers/api) — a free, public,
crowdsourced book database maintained by the Internet Archive.



## Known limitations

- Translations of a work are treated as separate entries rather than merged
  with the original, since reliably matching titles across languages is out
  of scope for this project.
- Duplicate entries for the same book can still slip through when the
  titles differ meaningfully — for example, a translated title, a
  retitled edition, or significant spelling variation — since
  deduplication relies on normalized title matching rather than semantic
  or cross-language comparison.
- Some entries are missing fields (publish year, page count, subjects) —
  these are handled gracefully but naturally reduce the completeness of
  certain analyses.