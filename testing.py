import requests


def search_google_books(query, max_results=5):
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


# Example usage
query = "Konji"
books_info = search_google_books(query)

# Print results
for idx, book in enumerate(books_info, 1):
    print(f"Book {idx}:")
    for key, value in book.items():
        print(f"{key}: {value}")
    print("\n" + "-" * 50 + "\n")
