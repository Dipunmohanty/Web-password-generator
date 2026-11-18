# Personality Passwords

A localhost password helper that creates memorable passwords based on a user's profile and selected password constraints.

## Structure

- `database/`: MySQL schema and database setup notes
- `backend/`: Flask API, SQLAlchemy models, and AI provider integration
- `frontend/`: HTML/CSS/JavaScript UI and Go HTTP server
- `Tests/test_cases.py`: synthetic-user and edge-case test suite; optional isolated test tables in MySQL

## How it works

1. A user creates an account with a username, password, name, date and place of birth, and answers to 10 randomly selected personality questions. Flask stores the account and profile answers in MySQL.
2. The signed-in user chooses **Create password** and answers 10 questions about password length, character constraints, theme, and style.
3. Flask sends the profile and password preferences as JSON to the configured OpenAI-compatible AI endpoint. The AI key and model configuration are read from backend environment variables.
4. The backend checks the generated password against the requested length and character constraints, encrypts it, and saves it under the user's chosen name.
5. The user can view, edit, or delete saved passwords. Go serves the frontend and forwards `/api/*` requests to Flask.

## Setup and run

1. Install the backend requirements: `python -m pip install -r backend/requirements.txt`.
2. Create the MySQL database using `database/schema.sql` and set `DATABASE_URL` to the connection string for that database.
3. Set `FLASK_SECRET_KEY` and `PASSWORD_FERNET_KEY`. Generate an encryption key with:

   ```powershell
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

4. Configure `AI_API_URL`, `AI_MODEL`, and `AI_API_KEY` in the environment where the Flask backend runs. Keep the API key private; do not commit it.
5. Start Flask from the project root: `python backend/app.py`.
6. In a separate terminal, start Go: `cd frontend; go run .`.
7. Open `http://127.0.0.1:8080`.

## Run tests

From the project root, run `python -m unittest discover -s Tests -v`. The tests use synthetic profiles, an isolated SQLite database, and a mocked AI generator; they do not call the external AI service or modify the application's MySQL tables.

To also save a test run in the same MySQL database, set `TEST_RESULTS_DATABASE_URL` to that database's MySQL connection URL, then run:

```powershell
python Tests/test_cases.py --persist-results
```

This creates two independent tables, `test_case_users` and `test_case_results`. The results table refers only to the test users table; neither table has a foreign key or other relationship to the application's `users`, `user_profiles`, or `saved_passwords` tables. Each test user has a `logs` field for failure details, and each result has a nullable `generated_password` field. Test AI responses are mocked: successful cases save a representative synthetic password, while failed/invalid generation cases save `NULL` and the failure reason.
