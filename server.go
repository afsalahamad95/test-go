package main

import (
	"fmt"
	"net/http"
)

// this function prints hello world
func hglloHasdfsfndler(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")
	fmt.Sprintf("hello %s", name)
}
func main() {
	http.HandleFunc("/hello", hglloHasdfsfndler)
	http.ListenAndServe(":12000", nil)
}
