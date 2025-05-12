package main

import (
	"fmt"
	"net/http"
)

// this function prints hello world
func hglloHandler(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")
	fmt.Println(name)
	fmt.Sprintf("hwello woeld")
	var x = 43
	fmt.Sprintf("x=%v", x)
	fmt.Println("hello world")
}
func main() {
	http.HandleFunc("/hello", hglloHandler)
	http.ListenAndServe(":12000", nil)
}
