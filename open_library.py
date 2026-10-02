import requests
import pandas as pd
import re
import plotly.express as px
from pathlib import Path
import webbrowser


search = "https://openlibrary.org/search.json"
author = "https://openlibrary.org/search/authors.json"
headers = {
    "User-Agent": "BooksAnalysisProject/1.0 (contact: marwalatyh)"
}

# getting author name as an input
def get_author_name():
    author_name = input(
    "Please enter the author's name.\n"
    " - Double-check the spelling.\n"
    " - Full name works best.\n"
    "Name: ").strip()

    while not author_name or author_name.isdigit() or not re.match(r"^([^\W\d_]|[\s\-\.'])+$", author_name):
        author_name = input("Please enter a valid name: ").strip()
        
    author_name = author_name.lower()
    return author_name


# checking if the author exists in the library
def find_author():
    name = get_author_name()
    params = {"q": name}
    try:
        r = requests.get(url=author, headers= headers, params=params, timeout=20)

    except Exception as e:
        print(f'Error connecting to Open Library: {e}')
        return None

    try:
        data = r.json()

    except Exception as e:
        print(f'Error reading the response: {e}')
        return None

    # filtering to eliminate the irrelevant authors that has the same name
    if data.get("docs"):
        candidates = []

        # 1st filtering layer is comparing the entry to the actual author's name
        for doc in data["docs"]:
            real_name = doc["name"].lower()

            if name == real_name:
                candidates.append(doc)
                            
            elif doc.get("alternate_names"):
                alternate_names = [alt.lower() for alt in doc["alternate_names"]]
                if name in alternate_names:
                    candidates.append(doc)
            
        if not candidates:
            print('There is no matching')
            return None
            
        if len(candidates) == 1:
            return candidates[0]

        # 2nd filtering layer, is elimintaing the candidates that miss the essential fileds
        required_fields = ["key", "name", "work_count"]
        valid_candidates = []
            
        for doc in candidates:
            if all(field in doc for field in required_fields):
                valid_candidates.append(doc)

        if not valid_candidates:
            print("Candidates found but missing required data.")
            return None
            
        if len(valid_candidates) == 1:
            return valid_candidates[0]
            
        if valid_candidates:
            return max(valid_candidates, key=lambda doc: doc["work_count"])

                    
    else:
        print(f"The author '{name}' has no data in Open Library")
        return None

# extract the general infos and author's key(ID)
def extract_author_data(doc):
    if doc:
        author_data = {}
        author_data['ID'] = doc['key']
        author_data['Name'] = doc['name']
        author_data['Birth Date'] = doc.get('birth_date')
        author_data['Death Date'] = doc.get('death_date')
        author_data['Top Subjects'] = doc.get('top_subjects')
        author_data['Top Work'] = doc.get('top_work')
        author_data['Total Work'] = doc.get('work_count')
                
        return author_data
    

# extracting all works found for this author ID, with duplicates
def get_author_works(author_data):
    if author_data:
        author_ID = author_data['ID']
        params = {
            "q": f"author_key:{author_ID}",
            "fields": "key,title,cover_i,edition_count,first_publish_year,publish_year,number_of_pages_median,subject", 
            "limit": 1000
        }

        try:
            r = requests.get(url=search, headers= headers, params=params, timeout=20)

        except Exception as e:
            print(f'Error connecting to Open Library: {e}')
            return None

        try:
            data = r.json()

        except Exception as e:
            print(f'Error reading the response: {e}')
            return None
        
        uncleaned_works = data.get('docs')

        if uncleaned_works:
            return uncleaned_works
        
        else:
            print(f"The author '{author_data['Name']}' has no work in Open Library.")
            return None


# grouping the duplicate works under one title, then compare them and choose one, according to specific criteria (includes all author works)
def clean_author_works(uncleaned_works):
    if uncleaned_works:
        # normalize all titles before grouping them
        cleaned_works = []
        for work in uncleaned_works:
            if work.get('title'):
                title = work['title'].lower()
                title = re.sub(r"[\"'’‘“”]", "", title)
                title = re.sub(r"[^\w\s]", " ", title)
                title = re.sub(r"\s+", " ", title).strip()

                work['norm_title'] = title
                cleaned_works.append(work)

        # grouping the duplicates by norm_title
        grouped_duplicates = {}

        for work in cleaned_works:
            key = work['norm_title']
            if key not in grouped_duplicates:
                grouped_duplicates[key] = [work]
            else:
                grouped_duplicates[key].append(work)

        # comparing the grouped books and choosing one:
        # tiebreak priority: oldest first_publish_year, then highest edition_count, then highest page count
        unique_works = {}

        for key, values in grouped_duplicates.items():
            if len(values) == 1:
                unique_works[key] = values[0]
            else:
                best = values[0]
                for value in values[1:]:
                    if value.get('first_publish_year', float('inf')) < best.get('first_publish_year', float('inf')):
                        best = value
                    elif value.get('first_publish_year', float('inf')) == best.get('first_publish_year', float('inf')):
                        if best.get('edition_count', 0) < value.get('edition_count', 0):
                            best = value
                        elif best.get('edition_count', 0) == value.get('edition_count', 0):
                            if value.get('number_of_pages_median', 0) > best.get('number_of_pages_median', 0):
                                best = value

                unique_works[key] = best

        books = []
        for key, value in unique_works.items():
            books.append(value)

        return books


# this will extract the works of the author during their lifetime (exclude the works after their death)
def lifetime_activity(author_data, books):
    if author_data and books:

        raw_birth = author_data.get('Birth Date')
        raw_death = author_data.get('Death Date')

        # BC authors can't be filtered by lifetime
        raw_dates = f"{raw_birth or ''} {raw_death or ''}".lower().replace(".", "")
        if "bc" in raw_dates:
            print("No data available for authors from the BC era.")
            return None

        # scenario 1: both exist, the author is deceased
        if raw_birth and raw_death:
            birth_date = int(raw_birth[-4:].strip())
            death_date = int(raw_death[-4:].strip())

        # scenario 2: the author is probably alive or the date is just missing
        elif raw_birth and not raw_death:
            birth_date = int(raw_birth[-4:].strip())
            death_date = float('inf')

        # scenario 3: the birth date is missing and the author is deceased
        elif raw_death and not raw_birth:
            birth_date = float('-inf')
            death_date = int(raw_death[-4:].strip())

        # scenario 4: both are missing
        else:
            birth_date = float('-inf')
            death_date = float('inf')

        lifetime_books = []
        for work in books:
            work_year = work.get('first_publish_year')
            if work_year is None:
                continue

            if birth_date < work_year <= death_date:
                lifetime_books.append(work)

        return lifetime_books

def data_retrieving_func():
    doc = find_author()
    author_data = extract_author_data(doc)
    uncleaned_works = get_author_works(author_data)
    books = clean_author_works(uncleaned_works)
    lifetime_books = lifetime_activity(author_data, books)

    all_data = {
        'author_data': author_data,
        'books': books,
        'lifetime_activity': lifetime_books
    }

    return all_data

#-------------------------------------------------------Data framing-----------------------------------------------------

pd.set_option('display.max_colwidth', 50)
pd.set_option('future.no_silent_downcasting', True)

# 1st DataFrame: the books in open library, cleaned from duplicates as much as possible
def author_works(all_data):
    if all_data:
        data = all_data.get('books')

        if data:
            books = []
            for d in data:
                book = {}
                #publish_year = d.get('publish_year')
                subject = d.get('subject')

                book['Title'] = d.get('title').title()
                book['First Publish Year'] = d.get('first_publish_year')
                book['Number of Editions'] = d.get('edition_count')
                #book['publish_year'] = (','.join(map(str, publish_year)) if publish_year else None)
                book['Average Number of Pages'] = d.get('number_of_pages_median')
                book['Book Subject'] = ','.join(subject) if subject else None

                books.append(book)

            author_books = pd.DataFrame(books).sort_values(by=['First Publish Year'])
            author_books['First Publish Year'] = author_books['First Publish Year'].astype('Int64')
            return author_books

# 2nd DataFrame: the works of the author during their lifetime 
def author_activity(all_data):
    if all_data:
        lifetime_works = all_data.get('lifetime_activity')

        if lifetime_works:
            books = []
            for d in lifetime_works:
                book = {}
                #publish_year = d.get('publish_year')
                subject = d.get('subject')
            
                book['Title'] = d.get('title').title()
                book['First Publish Year'] = d.get('first_publish_year')
                book['Number of Editions'] = d.get('edition_count')
                #book['publish_year'] = (','.join(map(str, publish_year)) if publish_year else None)
                book['Average Number of Pages'] = d.get('number_of_pages_median')
                book['Book Subject'] = ','.join(subject) if subject else None
            
                books.append(book)
            
            lifetime_books = pd.DataFrame(books)
            lifetime_books['First Publish Year'] = lifetime_books['First Publish Year'].astype('Int64')
            lifetime_books = lifetime_books.sort_values(by=['First Publish Year'])
            return lifetime_books


#-----------------------------------------------------Visualising--------------------------------------------------------


def style_figure(fig):
    fig.update_layout(template='plotly_white')
    fig.update_xaxes(showline=True, linewidth=1.5, linecolor='black', mirror=True)
    fig.update_yaxes(showline=True, linewidth=1.5, linecolor='black', mirror=True)
    fig.update_xaxes(title_text=f"<b>{fig.layout.xaxis.title.text}</b>")
    fig.update_yaxes(title_text=f"<b>{fig.layout.yaxis.title.text}</b>")
    return fig


# chart 1: bar chart, shows the author activity over time (books num per year)
def activity_over_time(lifetime_books):
    if lifetime_books is not None:
        books_per_year = lifetime_books.groupby("First Publish Year").size().reset_index(name = "Number of Books")
        fig = px.bar(books_per_year,
                     title="<b>Books Published Over Years (During The Author's Lifetime)</b>",
                     x = 'First Publish Year',
                     y = 'Number of Books',
                     labels={'First Publish Year': 'Year'},
                     color='Number of Books',
                     color_continuous_scale='Blues')
        fig.update_xaxes(tickvals=books_per_year['First Publish Year'], tickangle=-90)
        return style_figure(fig)

# chart 2: no. of editions per book
def editions_per_book(lifetime_books):
    if lifetime_books is not None:
        editions = lifetime_books[['Title','Number of Editions']].nlargest(20, 'Number of Editions')
        fig = px.bar(editions,
                     title= "<b>Editions Per Book</b>",
                     x = 'Number of Editions',
                     y = 'Title',
                     labels= {'Title':'Book'},
                     color='Number of Editions',
                     color_continuous_scale='Twilight')
        fig.update_yaxes(categoryorder='total ascending')
        return style_figure(fig)

# chart 3: no. of editions of a book over years
def editions_over_time(lifetime_books):
    if lifetime_books is not None:
        data = lifetime_books[['Title', 'First Publish Year', 'Number of Editions']].dropna()
        data = data[data['Number of Editions'] > 0]
        fig = px.scatter(data,
                         title= "<b>Editions Per Book Over Time</b>",
                         x='First Publish Year',
                         y='Number of Editions',
                         size='Number of Editions',
                         hover_name='Title',
                         size_max=40,
                         log_y=True,
                         labels={'First Publish Year': 'Year'},
                         color='Number of Editions',
                         color_continuous_scale='Sunset')
        fig.update_traces(marker=dict(sizemin=4, sizemode='area'))
        return style_figure(fig)
#----------------------------------------------------Building the report-------------------------------------------------
def build_tables(all_data, lifetime_books):

    if all_data:
        # 3rd DataFrame: the general data of the author
        author_data = all_data.get('author_data')
        if author_data:
            data = author_data.copy()
            del data['ID']
            del data['Top Subjects']
            info = pd.DataFrame([data]).T
            info.columns = ['Info']
                    
            top_subjects = author_data.get('Top Subjects')
            subjects = pd.DataFrame(top_subjects, columns=['Top Subjects']) if top_subjects else None
            death_date = author_data.get('Death Date')
    
            return {
                'info': info,
                'subjects': subjects,
                'lifetime': lifetime_books,
                # to prevent duplicating the tables if the author is alive.
                'all_works': author_works(all_data) if death_date else None,
                'death_missing': not death_date
            }


def shorten(lifetime_books, column, limit):
    df = lifetime_books.copy()
    df[column] = df[column].apply(
        lambda s: s if not isinstance(s, str) or len(s) <= limit else s[:limit].rstrip(", ") + "…")
    return df

def tidy(df):
    return df.astype(object).fillna('')


def build_report(tables, charts, path="report.html"):
    if not tables:
        return None

    parts = []

    # info + subjects tables side by side in one row
    info_html = "<div><h2>Author Info</h2>" + tidy(tables['info']).to_html(justify='left') + "</div>"
    subjects_html = ""
    if tables['subjects'] is not None:
        subjects_html = "<div><h2>Top Subjects</h2>" + tidy(tables['subjects']).to_html(index=False, justify='left') + "</div>"
    parts.append("<div class='row'>" + info_html + subjects_html + "</div>")

    if tables['lifetime'] is not None:
        parts.append("<h2>Works Published During the Author's Lifetime</h2>")
        if tables['death_missing']:
            parts.append("<p><i>Death date is missing. The author may still be alive, or the record is incomplete. Results include everything published.</i></p>")
        parts.append(tidy(shorten(shorten(tables['lifetime'], 'Book Subject', 500), 'Title', 100)).to_html(index=False, justify='left', classes='works'))

    charts = [fig for fig in charts if fig is not None]
    for i, fig in enumerate(charts):
        parts.append(fig.to_html(full_html=False, include_plotlyjs='cdn' if i == 0 else False))

    if tables['all_works'] is not None:
        parts.append("<h2>All Works Recorded in Open Library</h2>")
        parts.append(tidy(shorten(shorten(tables['all_works'], 'Book Subject', 500), 'Title', 100)).to_html(index=False, justify='left', classes='works'))

    style = """<style>
    .row { display: flex; gap: 40px; align-items: flex-start; }
    table { border-collapse: collapse; width: auto; }
    th, td { text-align: left; padding: 4px 10px; white-space: nowrap; }
    table.works td { max-width: 400px; white-space: normal; overflow-wrap: anywhere; }
    </style>"""

    html = ("<html><head><meta charset='utf-8'><title>Author Report</title>" + style + "</head>"
            "<body style='font-family: Arial; margin: 40px;'>"
            + "".join(parts) + "</body></html>")

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    webbrowser.open(Path(path).resolve().as_uri())

if __name__ == "__main__":
    all_data = data_retrieving_func()
    lifetime_books = author_activity(all_data)
    tables = build_tables(all_data, lifetime_books)
    activity = activity_over_time(lifetime_books)
    editions = editions_per_book(lifetime_books)
    editions_time = editions_over_time(lifetime_books)
    build_report(tables, [activity, editions, editions_time])


