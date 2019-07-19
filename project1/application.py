import os
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
app = Flask(__name__)

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)
# Set up database
engine = create_engine("postgres://snsivxsdzqtkta:65401c2ec42bfade5f608583283158d266fb31c101b1174efa41539a7bf14d14@ec2-107-21-216-112.compute-1.amazonaws.com:5432/dqk2d8r2irpgm")
db = scoped_session(sessionmaker(bind=engine))

@app.route("/")
def index():
    status="Loggedout"
    try:
        user_email=session["user_email"]
        status=""
    except KeyError:
        user_email=""
    return render_template("index.html", status=status, user_email=user_email)

@app.route("/login",methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("Email")
        # Checking if the user is registered
        if db.execute("SELECT id FROM users WHERE email= :email", {"email": email}).fetchone() is not None:
            return render_template("login.html", work="Login",error_message="The user has already registered. Please Login.")
        password = request.form.get("Password")
        retype = request.form.get("RePassword")
        if password==retype:
            db.execute("INSERT INTO users (email, password) VALUES (:email, :password)",{"email": email, "password": generate_password_hash(password)})
            db.commit()
            return render_template("login.html", work="Login", message="Success")
        return render_template("login.html", work="Register", error_message="password not match")
    return render_template("login.html", work="Login")


@app.route("/logout")
def logout():
    try:
        session.pop("user_email")
    except KeyError:
        return render_template("login.html", work="Login", error_message="Please Login First")
    return render_template("login.html",  work="Login")

@app.route("/forgotPassword",methods=["GET","POST"])
def forgotPassword():
    if request.method == "POST":
        email = request.form.get("Email")
        user=db.execute("SELECT email FROM users WHERE email= :email",{"email": email}).fetchone()
        if user is None:
            return render_template("login.html", error_message="Look like! You are not registered yet",work="Register")
        password = request.form.get("Password")
        retype = request.form.get("RePassword")
        if password==retype:
            db.execute("UPDATE users SET password = :password WHERE email = :email",{"password": generate_password_hash(password), "email": email})
            db.commit()
            return render_template("success.html")
        return render_template("login.html",error_message="password not match",work="forgotPassword")
    return render_template("login.html",work="forgotPassword")

@app.route("/search", methods=["GET", "POST"])
def search():
    # Request from /login to log a user in
    if request.method == "POST":
        # Checking if the user is present, if not present show error message and redirect to /register
        email = request.form.get("Email")
        user = db.execute("SELECT id, password FROM users WHERE email= :email", {"email": email}).fetchone()
        if user is None:
            return render_template("login.html", error_message="Look like! You are not registered yet",work="Register")
        password = request.form.get("Password")
        if not check_password_hash(user.password, password):
            return render_template("login.html", error_message="Email or password is incorrect", work="Login")
        session["user_email"]=email
    if request.method == "GET":
        if "user_email" not in session:
            return render_template("login.html", error_message="Please Login First", work="Login")
        else:
            email=session["user_email"]
    return render_template("search.html", user_email=email)

@app.route("/register")
def register():
    return render_template("login.html", work="Register")

@app.route("/booklist", methods=["POST"])
def booklist():
    if "user_email" not in session:
        return render_template("login.html", error_message="Please Login First", work="Login")

    book_column = request.form.get("book_column")
    query = request.form.get("query")
    if query=="":
        return render_template("search.html", user_email=session["user_email"],error_message="search field shouldn't be empty")
    if book_column == "year":
        try:
            query=int(query)
            book_list = db.execute("SELECT * FROM books WHERE year = :query", {"query": query}).fetchall()
        except:
            return render_template("search.html", user_email=session["user_email"],error_message="Year should be number")
    else:
        book_list = db.execute("SELECT * FROM books WHERE UPPER(" + book_column + ") = :query ORDER BY title",
                               {"query": query.upper()}).fetchall()

    # Is whole of the info i.e. ISBN, title matches...
    if len(book_list):
        return render_template("booklist.html", book_list=book_list, user_email=session["user_email"],message="Matching Results")

    elif book_column != "year":
        error_message = "We couldn't find the books you searched for."
        book_list = db.execute("SELECT * FROM books WHERE UPPER(" + book_column + ") LIKE :query ORDER BY title",
                               {"query": "%" + query.upper() + "%"}).fetchall()
        if not len(book_list):
            return render_template("booklist.html", error_message=error_message,user_email=session["user_email"])
        message = "You might be searching"
        return render_template("booklist.html",book_list=book_list, message=message, user_email=session["user_email"])
    else:
        return render_template("booklist.html", error_message="We didn't find any book with the year you typed. Please check for errors and try again.",user_email=session["user_email"])

@app.route("/detail/<int:book_id>", methods=["GET", "POST"])
def detail(book_id):
    if "user_email" not in session:
        return render_template("login.html", error_message="Please Login First", work="Login")

    book = db.execute("SELECT * FROM books WHERE id = :book_id", {"book_id": book_id}).fetchone()
    if book is None:
        return render_template("error.html", error_message="We got an invalid book id. Please check for the errors and try again.")

    # When review if submitted for the book.
    if request.method == "POST":
        user_email = session["user_email"]
        user = db.execute("SELECT id,password FROM users WHERE email= :email", {"email": user_email}).fetchone()

        rating = request.form.get("rating")
        comment = request.form.get("comment")
        if db.execute("SELECT id FROM reviews WHERE user_id = :user_id AND book_id = :book_id",
                      {"user_id": user.id, "book_id": book_id}).fetchone() is None:
            db.execute(
                "INSERT INTO reviews (user_id, book_id, rating, comment) VALUES (:user_id, :book_id, :rating, :comment)",
                {"book_id": book.id, "user_id": user.id, "rating": rating, "comment": comment})
        else:
            db.execute(
                "UPDATE reviews SET comment = :comment, rating = :rating WHERE user_id = :user_id AND book_id = :book_id",
                {"comment": comment, "rating": rating, "user_id": user.id, "book_id": book_id})
        db.commit()

    """Goodreads API"""
    # Processing the json data
    res = requests.get("https://www.goodreads.com/book/review_counts.json",
                       params={"key": "c1ZkQ09kDLcoRaB3FVUFQ", "isbns": book.isbn}).json()["books"][0]

    ratings_count = res["ratings_count"]
    average_rating = res["average_rating"]
    reviews = db.execute("SELECT * FROM reviews WHERE book_id = :book_id", {"book_id": book.id}).fetchall()
    users = []
    for review in reviews:
        email = db.execute("SELECT email FROM users WHERE id = :user_id", {"user_id": review.user_id}).fetchone().email
        users.append((email, review))

    return render_template("detail.html", book=book, users=users,length=len(users),
                           ratings_count=ratings_count, average_rating=average_rating, user_email=session["user_email"])


@app.route("/api/<ISBN>", methods=["GET"])
def api(ISBN):
    book = db.execute("SELECT * FROM books WHERE isbn = :ISBN", {"ISBN": ISBN}).fetchone()
    if book is None:
        return render_template("error.html", error_message="We got an invalid ISBN. Please check for the errors and try again.")
    reviews = db.execute("SELECT * FROM reviews WHERE book_id = :book_id", {"book_id": book.id}).fetchall()
    count = 0
    rating = 0
    for review in reviews:
        count += 1
        rating += review.rating
    if count:
        average_rating = rating / count
    else:
        average_rating = 0

    return jsonify(
        title=book.title,
        author=book.author,
        year=book.year,
        isbn=book.isbn,
        review_count=count,
        average_score=average_rating
    )
