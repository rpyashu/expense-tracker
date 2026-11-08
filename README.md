# expense-tracker
Personal finance tracker built with Flask, SQLite and JavaScript.
# SpendWise – Expense Tracker

A responsive personal finance web app built with Flask and SQLite.
Set your yearly income, add entries, and see what's left.

## Features
- Register and log in (hashed passwords)
- Yearly income plans that can change during the year (raise or new job)
- Six entry types: expense, extra income, borrowed, loan repaid, lent, savings
- Payment modes and custom categories
- Overview page with yearly balance and progress bar
- Editable spreadsheet-style table with auto-save
- Monthly summary with category breakdown and charts
- Export to Excel (CSV)
- Responsive, minimal design for desktop and mobile

## Tech stack
Python, Flask, SQLite, HTML, CSS, JavaScript, Chart.js

## Screenshots
![Overview]<img width="1916" height="907" alt="overview page" src="https://github.com/user-attachments/assets/25172578-b6c7-4b7b-ab15-7f3b1180da77" />

![Add entry]<img width="1912" height="907" alt="add expence page" src="https://github.com/user-attachments/assets/36e3f743-aeca-4049-a2da-3dc7dab87c67" />

![Sheet]<img width="1917" height="552" alt="excel sheet" src="https://github.com/user-attachments/assets/e7a8e1fa-d634-4a03-99b7-2bb395a6f2d2" />

![Monthly summary]<img width="1890" height="903" alt="monthly expense overview" src="https://github.com/user-attachments/assets/09cc9964-eb05-4f50-b045-39b812c542a5" />

![signup page]<img width="1882" height="873" alt="signup page" src="https://github.com/user-attachments/assets/78f1ea48-2cf0-4b88-8dd8-bd3b57a1b66d" />


## Run locally
```bash
python -m venv venv
venv\Scripts\activate
pip install flask
python app.py
```
Then open http://127.0.0.1:5000

## Planned
- Offline-first mobile version (PWA)
