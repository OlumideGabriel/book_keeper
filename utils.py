import requests
import json

def search_google_books(query, max_results=5):
    """Searches Google Books API for books matching the query."""
    base_url = "https://www.googleapis.com/books/v1/volumes"
    params = {
        "q": query,
        "maxResults": max_results
    }

    response = requests.get(base_url, params=params)

    if response.status_code == 200:
        books = response.json().get("items", [])

        results = []
        for book in books:
            volume_info = book.get("volumeInfo", {})

            # Extract key information
            title = volume_info.get("title", "N/A")
            authors = ", ".join(volume_info.get("authors", ["Unknown"]))
            publisher = volume_info.get("publisher", "N/A")
            published_date = volume_info.get("publishedDate", "N/A")
            description = volume_info.get("description", "No description available")
            thumbnail = volume_info.get("imageLinks", {}).get("thumbnail", "No image available")

            # Extract ISBN
            industry_identifiers = volume_info.get("industryIdentifiers", [])
            isbn_10 = isbn_13 = "N/A"
            for identifier in industry_identifiers:
                if identifier["type"] == "ISBN_10":
                    isbn_10 = identifier["identifier"]
                elif identifier["type"] == "ISBN_13":
                    isbn_13 = identifier["identifier"]

            # Append to results
            results.append({
                "Title": title,
                "Authors": authors,
                "Publisher": publisher,
                "Published Date": published_date,
                "ISBN-10": isbn_10,
                "ISBN-13": isbn_13,
                "Description": description,
                "Thumbnail": thumbnail,
            })

        return results
    else:
        return f"Error: {response.status_code}, {response.text}"


def fetch_book_details_from_google_books_by_isbn(isbn):
    """Fetches book details from Google Books API using ISBN."""
    base_url = "https://www.googleapis.com/books/v1/volumes"
    query = f'isbn:{isbn}'
    params = {
        "q": query,
        "maxResults": 1
    }

    response = requests.get(base_url, params=params)

    if response.status_code == 200:
        data = response.json()
        items = data.get("items", [])

        if not items:
            return None

        volume_info = items[0].get("volumeInfo", {})
        # Extract key information
        book_info = {
            "title": volume_info.get("title", "N/A"),
            "author": ", ".join(volume_info.get("authors", ["Unknown"])),
            "publisher": volume_info.get("publisher", "N/A"),
            "published_date": volume_info.get("publishedDate", "N/A"),
            "description": volume_info.get("description", "No description available"),
            "thumbnail": volume_info.get("imageLinks", {}).get("thumbnail", "No image available"),
            "isbn": isbn,
        }
        return book_info

    else:
        print(f"Error {response.status_code}: {response.text}")
        return None


def fetch_book_details_from_isbn_list(isbn_list):
    results = []

    for isbn_key, isbn_value in isbn_list.items():
        book_details = fetch_book_details_from_google_books_by_isbn(isbn_value)
        if book_details:
            results.append(book_details)
    return results
