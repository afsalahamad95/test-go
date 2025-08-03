package main

import (
	"fmt"
	"net/http"
)

// this function prints hello world
func hgrrtlloHandler(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")
	name = fmt.Sprintf("hello %s", name)
	fmt.Println(name)
}
func main() {
	http.HandleFunc("/hello", hgrrtlloHandler)
	http.ListenAndServe(":12000", nil)
}
