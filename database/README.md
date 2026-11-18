# Database

MySQL 8.0 is the persistence engine. Apply the schema with the local MySQL client:

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p < schema.sql
```

Do not store plaintext passwords: account passwords are hashed and saved passwords are Fernet-encrypted by the Flask backend.
