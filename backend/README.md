# Backend

Flask and SQLAlchemy provide the API and MySQL ORM. Install dependencies and create a Fernet key:

```powershell
python -m pip install -r requirements.txt
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set `DATABASE_URL`, `FLASK_SECRET_KEY`, and `PASSWORD_FERNET_KEY` in the shell or in a process environment.

Password generation additionally requires `AI_API_URL`, `AI_MODEL`, and `AI_API_KEY`. These values are read only from the backend process environment; do not place a real API key in source control.

Run the synthetic-user tests from the project root with `python -m unittest discover -s Tests -v`. To save the results to the independent test tables in MySQL, set `TEST_RESULTS_DATABASE_URL` and run `python Tests/test_cases.py --persist-results`.
