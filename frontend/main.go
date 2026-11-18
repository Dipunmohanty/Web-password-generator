package main

import (
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"strings"
)

func main() {
	port := env("HTTP_PORT", "8080")
	flaskURL := env("FLASK_URL", "http://127.0.0.1:5000")

	flask, err := url.Parse(flaskURL)
	if err != nil {
		log.Fatal(err)
	}
	apiProxy := httputil.NewSingleHostReverseProxy(flask)

	staticDir := "."
	if _, err := os.Stat("frontend"); err == nil {
		staticDir = "frontend"
	}
	fileServer := http.FileServer(http.Dir(staticDir))

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if strings.HasPrefix(r.URL.Path, "/api/") {
			apiProxy.ServeHTTP(w, r)
			return
		}
		fileServer.ServeHTTP(w, r)
	})

	log.Printf("Personality Passwords is listening on http://127.0.0.1:%s", port)
	log.Fatal(http.ListenAndServe("127.0.0.1:"+port, nil))
}

func env(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}
