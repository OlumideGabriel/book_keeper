from flask import Flask, request, render_template, jsonify, flash, redirect, url_for, current_app, session
from config import API_KEYS
from openai import OpenAI
import utils
import json
from flask_wtf.csrf import CSRFProtect
from flask_wtf import FlaskForm
from flask_migrate import Migrate
from wtforms import StringField, DateField, SelectField, validators, FloatField
from wtforms.validators import DataRequired, NumberRange
import secrets
from flask_sqlalchemy import SQLAlchemy
from werkzeug.exceptions import BadRequest
import os
import requests
from datetime import datetime
from data_models import db, Author, Book

# Initialize Flask app
app = Flask(__name__)

# After creating your Flask app
app.config['SECRET_KEY'] = secrets.token_hex(32)  # Replace with a real secret key
csrf = CSRFProtect(app)

# Configure database
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(BASE_DIR, "data", "library.sqlite")
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database with the app
db.init_app(app)
migrate = Migrate(app, db)


def fetch_book_details_from_google_books(title, author_name):
    """
    Fetch ISBN-10, ISBN-13, and the thumbnail URL for a book using the Google Books API.

    :param title: Title of the book
    :param author_name: Author of the book
    :return: Dictionary with ISBN-10, ISBN-13, and thumbnail URL or None if not found
    """
    base_url = "https://www.googleapis.com/books/v1/volumes"
    query = f'intitle:{title} inauthor:{author_name}'
    params = {
        "q": query,
        "maxResults": 1,  # Fetch only the first result
        "fields": "items(volumeInfo/industryIdentifiers,volumeInfo/imageLinks)",  # Get ISBNs and image links
    }

    response = requests.get(base_url, params=params)

    if response.status_code == 200:
        data = response.json()
        items = data.get("items", [])

        if not items:
            return None  # No book found

        volume_info = items[0].get("volumeInfo", {})
        industry_identifiers = volume_info.get("industryIdentifiers", [])
        image_links = volume_info.get("imageLinks", {})

        isbn_data = {"ISBN-10": "N/A", "ISBN-13": "N/A", "Thumbnail": None}
        for identifier in industry_identifiers:
            if identifier["type"] == "ISBN_10":
                isbn_data["ISBN-10"] = identifier["identifier"]
            elif identifier["type"] == "ISBN_13":
                isbn_data["ISBN-13"] = identifier["identifier"]

        # Add the thumbnail URL
        isbn_data["Thumbnail"] = image_links.get("thumbnail", None)

        return isbn_data

    else:
        print(f"Error {response.status_code}: {response.text}")
        return None


@app.context_processor
def inject_current_year():
    """ Injects the current year into the template context."""
    return {'current_year': datetime.now().year}


@app.context_processor
def inject_counts():
    """ Injects total counts of books and authors into the template context."""
    return {
        'total_books_count': Book.query.count(),
        'total_authors_count': Author.query.count()
    }


# Convert string to date utility function
def str_to_date(date_str):
    return datetime.strptime(date_str, '%Y-%m-%d').date()


# Populate and create the database
def initialize_db():
    with app.app_context():
        db.create_all()  # Create tables for Author and Book
        db.session.commit()


def sort_books_by(sort_key='title'):
    """
    Sort books by title or author's name.

    :param sort_key: 'title' or 'author'
    :return: List of Book objects sorted accordingly
    """
    if sort_key == 'author':
        books = db.session.execute(
            db.select(Book).join(Author).order_by(Author.name)
        ).scalars().all()
    else:  # Default: sort by title
        books = db.session.execute(
            db.select(Book).order_by(Book.title)
        ).scalars().all()

    return books


def get_book_thumbnail(isbn=None):
    """
    Fetch the thumbnail URL of a book using its ISBN from the Google Books API.
    If no ISBN is provided or no thumbnail is found, return a default placeholder.
    """
    default_thumbnail = "https://upittpress.org/wp-content/themes/pittspress/images/no_cover_available.png"

    if not isbn:
        return default_thumbnail

    base_url = "https://www.googleapis.com/books/v1/volumes"
    params = {
        "q": f"isbn:{isbn}",
        "maxResults": 1,
        "fields": "items(volumeInfo/imageLinks)"
    }

    response = requests.get(base_url, params=params)

    if response.status_code == 200:
        data = response.json()
        items = data.get("items", [])

        if items:
            image_links = items[0].get("volumeInfo", {}).get("imageLinks", {})
            return image_links.get("thumbnail", default_thumbnail)

    return default_thumbnail


class EditBookForm(FlaskForm):
    title = StringField('Title', validators=[validators.InputRequired()])
    publication_date = DateField('Publication Date', format='%Y-%m-%d', validators=[validators.InputRequired()])
    author_id = SelectField('Author', coerce=int, validators=[validators.InputRequired()])
    isbn = StringField('ISBN')
    thumbnail = StringField('Cover Image URL')
    rating = FloatField('Rating (1-10)',
                        validators=[NumberRange(min=1, max=10, message="Rating must be between 1 and 10")])


@app.route('/get_thumbnail')
def get_thumbnail():
    try:
        isbn = request.args.get('isbn')
        title = request.args.get('title')
        author = request.args.get('author')

        # First try with ISBN if available
        if isbn:
            thumbnail_url = get_book_thumbnail(isbn)
            if thumbnail_url != "https://upittpress.org/wp-content/themes/pittspress/images/no_cover_available.png":
                return jsonify({'thumbnail': thumbnail_url})

        # If ISBN didn't work or isn't available, try with title and author
        if title and author:
            base_url = "https://www.googleapis.com/books/v1/volumes"
            params = {
                "q": f"intitle:{title}+inauthor:{author}",
                "maxResults": 1,
                "fields": "items(volumeInfo/imageLinks)"
            }

            response = requests.get(base_url, params=params)
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                if items:
                    image_links = items[0].get("volumeInfo", {}).get("imageLinks", {})
                    thumbnail_url = image_links.get("thumbnail", "")
                    if thumbnail_url:
                        return jsonify({'thumbnail': thumbnail_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    # If nothing found, return the default
    return jsonify({'thumbnail': "https://upittpress.org/wp-content/themes/pittspress/images/no_cover_available.png"})


@app.route('/')
def home():
    sort_by = request.args.get('sort_by', 'title')
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()

    # Start the base query
    query = db.select(Book).join(Author)

    # If there’s a search term, filter by title or author name using LIKE
    if search_query:
        like_pattern = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Book.title.ilike(like_pattern),
                Author.name.ilike(like_pattern)
            )
        )

    # Apply sorting
    if sort_by == "author":
        query = query.order_by(Author.name)
    else:
        query = query.order_by(Book.title)

    # Pagination: 10 books per page
    pagination = db.paginate(query, page=page, per_page=10)

    # Get current page’s books
    books_page = pagination.items

    # Get total counts
    total_books_count = Book.query.count()  # Assuming you're using SQLAlchemy
    total_authors_count = Author.query.count()  # Or however you count authors

    # Create the list of books with thumbnails
    books_with_thumbnails = [
        {
            "id": book.id,
            "title": book.title,
            "author": book.author.name,
            "author_id": book.author.id,
            "publication_date": book.publication_date,
            "thumbnail": book.thumbnail,
            "isbn": book.isbn,
        }
        for book in books_page
    ]

    # If searching and no results
    no_results = search_query and not books_with_thumbnails

    return render_template(
        'home.html',
        books=books_with_thumbnails,
        total_books_count=total_books_count,
        total_authors_count=total_authors_count,
        sort_by=sort_by,
        pagination=pagination,
        search=search_query,
        no_results=no_results
    )


@app.route('/authors')
def list_authors():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()

    # Start the base query
    query = db.select(Author)

    # If there's a search term, filter by name
    if search_query:
        like_pattern = f"%{search_query}%"
        query = query.filter(Author.name.ilike(like_pattern))

    # Order by name and paginate
    query = query.order_by(Author.name)
    pagination = db.paginate(query, page=page, per_page=12)

    # Get current page's authors
    authors_page = pagination.items

    # Count books for each author
    authors_with_counts = []
    for author in authors_page:
        book_count = len(author.books)
        authors_with_counts.append({
            "id": author.id,
            "name": author.name,
            "book_count": book_count,
            "birth_date": author.birth_date,
            "date_of_death": author.date_of_death
        })

    # If searching and no results
    no_results = search_query and not authors_with_counts

    return render_template(
        'authors.html',
        authors=authors_with_counts,
        pagination=pagination,
        search=search_query,
        no_results=no_results
    )


@app.route('/add_author', methods=['GET', 'POST'])
def add_author():
    """
    Handles adding a new author to the database.
    Accepts both form data (via POST) and provides a simple form (via GET).
    """
    if request.method == 'POST':
        try:
            # Retrieve form data
            name = request.form.get('name')
            birth_date = request.form.get('birth_date')
            date_of_death = request.form.get('date_of_death')

            # Validate required fields
            if not name or not birth_date:
                return jsonify({'error': 'Name and birth date are required.'}), 400

            # Convert dates from strings to datetime objects
            birth_date_obj = datetime.strptime(birth_date, '%Y-%m-%d').date()
            date_of_death_obj = (
                datetime.strptime(date_of_death, '%Y-%m-%d').date()
                if date_of_death
                else None
            )

            # Create and save a new author
            new_author = Author(name=name, birth_date=birth_date_obj, date_of_death=date_of_death_obj)
            db.session.add(new_author)
            db.session.commit()

            return render_template(
                'add_author.html',
                authors=Author.query.all(),
                success_message="Author added successfully!"
            )

        except Exception as e:
            # Handle any server-side error
            return jsonify({'error': f'An error occurred: {str(e)}'}), 500

    # Render the HTML form if the request is a GET
    return render_template('add_author.html')  # Assuming the form is saved as a template


@app.route('/author/<int:author_id>/delete', methods=['POST'])
def delete_author(author_id):
    """Deletes an author and all associated books from the database."""
    try:
        author = Author.query.get_or_404(author_id)
        db.session.delete(author)
        db.session.commit()
        flash('Author and all associated books deleted successfully!', 'success')
        return redirect(url_for('list_authors'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting author: {str(e)}', 'danger')
        return redirect(url_for('list_authors'))


@app.route('/add_book', methods=['GET', 'POST'])
def add_book():
    if request.method == 'GET':
        # Fetch all authors for the dropdown
        authors = Author.query.all()
        return render_template('add_book.html', authors=authors)

    try:
        # Retrieve form data
        title = request.form.get('title')
        publication_date = request.form.get('publication_date')
        author_id = request.form.get('author_id')

        if not title or not publication_date or not author_id:
            return jsonify({'error': 'Title, publication date, and author ID are required.'}), 400

        # Convert publication date to a datetime object
        publication_date_obj = datetime.strptime(publication_date, '%Y-%m-%d').date()

        # Check if the author exists
        author = Author.query.get(author_id)
        if not author:
            return jsonify({'error': 'Author does not exist.'}), 404

        # Fetch ISBN dynamically using Open Library API
        book_details = fetch_book_details_from_google_books(title, author.name)

        # Check if the book isbn exists
        book_isbn = Book.query.filter_by(isbn=book_details['ISBN-13']).first()
        if book_isbn:
            return render_template(
                'add_book.html',
                authors=Author.query.all(),
                danger_message="Book already exists!"
            )

        # After getting book_details from Google Books API
        thumbnail_isbn = get_book_thumbnail(book_details['ISBN-13'])

        # Create and save the new book
        new_book = Book(
            title=title,
            publication_date=publication_date_obj,
            isbn=book_details['ISBN-13'],
            thumbnail=thumbnail_isbn,  # Store the thumbnail URL
            author=author,

        )
        db.session.add(new_book)
        db.session.commit()

        return render_template(
            'add_book.html',
            authors=Author.query.all(),
            success_message="Book added successfully!"
        )

    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500


@app.route('/book/<int:book_id>/edit', methods=['GET', 'POST'])
def edit_book(book_id):
    book = Book.query.get_or_404(book_id)
    authors = Author.query.all()

    # Create form and populate choices
    form = EditBookForm()
    form.author_id.choices = [(a.id, a.name) for a in authors]

    if request.method == 'GET':
        # Pre-populate form with current book data
        form.title.data = book.title
        form.publication_date.data = book.publication_date
        form.author_id.data = book.author_id
        form.isbn.data = book.isbn
        form.thumbnail.data = book.thumbnail
        form.rating.data = book.rating  # Add this line for the rating field

    if form.validate_on_submit():
        try:
            book.title = form.title.data
            book.publication_date = form.publication_date.data
            book.author_id = form.author_id.data
            book.isbn = form.isbn.data
            book.thumbnail = form.thumbnail.data
            book.rating = form.rating.data  # Add this line for the rating field

            db.session.commit()
            flash('Book updated successfully!', 'success')
            return redirect(url_for('book_detail', book_id=book.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating book: {str(e)}', 'danger')

    return render_template(
        'edit_book.html',
        book=book,
        form=form,
        publication_date=book.publication_date.strftime('%Y-%m-%d') if book.publication_date else ''
    )


@app.route('/book/<int:book_id>/delete', methods=['POST'])
def delete_book(book_id):
    try:
        # Get the book to delete
        book = Book.query.get_or_404(book_id)
        author = book.author

        # Delete the book
        db.session.delete(book)

        # Check if author has no more books
        if not author.books:  # If author.books is empty
            db.session.delete(author)

        db.session.commit()
        flash('Book deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting book: {str(e)}', 'danger')

    return redirect(url_for('home'))


@app.route('/favorite-books')
def favorite_books():
    """
    Fetches all books with a rating of 7.0 or above.
    Returns a list of dictionaries containing book details.
    """
    books = Book.query.filter(Book.rating >= 7).all()
    fav_books = [{
        'id': book.id,
        'title': book.title.title(),
        'author': book.author.name,
        'publication_date': book.publication_date,
        'isbn': book.isbn,
        'thumbnail': book.thumbnail,
        'rating': book.rating
    } for book in books]

    return render_template('favorite_books.html', favorite_books=fav_books)


def get_ai_recommendation_by_isbn(books_data):
    url = "https://chatgpt-42.p.rapidapi.com/gpt4o"

    prompt = f"""Based on any two random books from this list of books:
    {json.dumps(books_data, indent=2)}, Suggest 5 similar books that users might enjoy.
      Please provide only the ISBNs of the books when possible in 
      this exact JSON format: book1:ISBN, book_2:ISBN, book_3:ISBN, book_4:ISBN, book_5:ISBN"""

    headers = {
        "content-type": "application/json",
        "X-RapidAPI-Key": API_KEYS['rapidapi'],
        "X-RapidAPI-Host": "chatgpt-42.p.rapidapi.com"
    }

    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json().get('result', 'No recommendations could be generated')


@csrf.exempt
@app.route('/suggest-book', methods=['GET', 'POST'])
def suggest_book():
    if request.method == 'POST':
        # Get favorite books (rating >= 7.0)
        fav_books = Book.query.filter(Book.rating >= 7).all()

        if not fav_books:
            flash("You don't have any favorite books (rating 7.0 or above)", "warning")
            return redirect(url_for('suggest_book'))

        books_data = [{
            'isbn': book.isbn
        } for book in fav_books]

        try:
            recommendation = get_ai_recommendation_by_isbn(books_data)
            rec_books_split = recommendation.split('```json')[1].split('```')[0].strip()
            rec_books_dict = json.loads(rec_books_split)

            # Extract only the ISBNs from the recommendation
            recommended_books = utils.fetch_book_details_from_isbn_list(rec_books_dict)

            return render_template('suggest_book.html',
                                   recommended_books=recommended_books,
                                   recommendation=recommendation,
                                   favorite_books=fav_books)
        except Exception as e:
            flash(f"Failed to get recommendations: {str(e)}", "danger")

    # GET request - show all books
    all_books = Book.query.all()
    fav_books = Book.query.filter(Book.rating >= 7).all()
    return render_template('suggest_book.html', all_books=all_books, favorite_books=fav_books)


@app.route('/book/<int:book_id>')
def book_detail(book_id):
    book = Book.query.get_or_404(book_id)
    return render_template('book_detail.html', book=book)


# Error handling and rendering error templates
def render_error_template(code, message, description):
    return render_template(
        "error.html",
        error_code=code,
        error_message=message,
        error_description=description,
        current_year=datetime.now().year
    ), code

@app.errorhandler(BadRequest)
def handle_csrf_error(e):
    if 'CSRF token' in str(e.description):
        return render_error_template(400, "Bad Request", e.description)
    return render_error_template(400, "Bad Request", "Invalid request.")

@app.errorhandler(400)
def bad_request(error):
    return render_error_template(400, "Bad Request", str(error))

@app.errorhandler(401)
def unauthorized(error):
    return render_error_template(401, "Unauthorized", "You are not authorized to access this resource.")

@app.errorhandler(403)
def forbidden(error):
    return render_error_template(403, "Forbidden", "Access to this resource is denied.")

@app.errorhandler(404)
def page_not_found(error):
    return render_error_template(404, "Page Not Found", "The page you are looking for does not exist.")

@app.errorhandler(405)
def method_not_allowed(error):
    return render_error_template(405, "Method Not Allowed", "The method is not allowed for this URL.")

@app.errorhandler(500)
def internal_server_error(error):
    return render_error_template(500, "Internal Server Error", "An unexpected error occurred.")

@app.errorhandler(ValueError)
def handle_value_error(error):
    return render_error_template(400, "Value Error", str(error))

@app.errorhandler(KeyError)
def handle_key_error(error):
    return render_error_template(400, "Key Error", str(error))

@app.errorhandler(TypeError)
def handle_type_error(error):
    return render_error_template(400, "Type Error", str(error))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(port=5008, host='0.0.0.0', debug=True)
