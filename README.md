# DermHub

DermHub is a simple online dermatology consultation web application. Users select a primary skin concern, answer follow-up questions, optionally upload images, and receive a response via email from a dermatologist.

## Features

- User signup & login (with password hashing)
- Select a main skin concern
- Automatic follow-up questions based on the concern
- Image upload for affected areas
- Stores consultation responses in a database
- Sends confirmation / instructions email via Mailgun
- Clean, mobile-friendly Bootstrap UI

## Tech Stack

- **Backend:** Python, Flask, Flask-WTF, SQLAlchemy
- **Database:** PostgreSQL
- **Frontend:** Jinja templates, Bootstrap 5
- **Auth:** Flask session + bcrypt password hashing
- **Email:** Mailgun API
- **Testing:** pytest

## Getting Started


### 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/DermHub.git
cd DermHub

### 2. Create & Activate Virtual Environment
python3 -m venv venv
source venv/bin/activate      # Mac/Linux
venv\Scripts\activate         # Windows

### 3. Install Requirements

pip install -r requirements.txt




### 4. Set up the database
createdb dermhubdb

### 5. Run the app
flask run


### 6. Visit in your browser :

http://localhost:5000

Running Tests
createdb dermhub_test
pytest -q

### 7. Project Structure
Capstone1/
│ app.py
│ models.py
│ requirements.txt
│ .env
│ README.md
├── static/
├── templates/
└── tests/

Future Improvements

Doctor/admin dashboard to review consultations

Medical history intake

Store and view past consultations


Optional AI image analysis suggestions
