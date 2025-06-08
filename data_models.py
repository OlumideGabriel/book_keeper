from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Author(db.Model):
    __tablename__ = 'authors'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    birth_date = db.Column(db.Date, nullable=False)
    date_of_death = db.Column(db.Date, nullable=True)

    # Relationship with the Book model
    books = db.relationship('Book', backref='author', cascade='all, delete-orphan', lazy=True)

    def __repr__(self):
        return f"<Author(id={self.id}, name='{self.name}')>"


class Book(db.Model):
    __tablename__ = 'books'

    id = db.Column(db.Integer, primary_key=True,  autoincrement=True)
    title = db.Column(db.String(200), nullable=False)
    publication_date = db.Column(db.Date, nullable=False)
    isbn = db.Column(db.String(13), nullable=True)  # ISBN for the book cover
    author_id = db.Column(db.Integer, db.ForeignKey('authors.id'), nullable=False)
    thumbnail = db.Column(db.String(500), nullable=True)  # URL for book cover thumbnail
    date_added = db.Column(db.Date, nullable=True, default=datetime.utcnow)
    rating = db.Column(db.Float, nullable=True)

    def __repr__(self):
        return f"<Book(id={self.id}, title='{self.title}', author_id={self.author_id})>"


