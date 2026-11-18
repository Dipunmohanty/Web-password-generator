# Frontend

The frontend is HTML/CSS/JavaScript. The Go server explicitly handles HTTP routes, serves these static files, and proxies `/api/*` requests to Flask.

```powershell
cd frontend
go run .
```
